import time
import socket
import threading
import json
import logging
from typing import Tuple, Optional, Dict, Any
import os
from apa102 import APA102
import gpiozero

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# LED Settings
NUM_LEDS = 3
LEDS_GPIO = 12

# Define standard colors
_BLACK = (0, 0, 0)
_WHITE = (255, 255, 255)
_RED = (255, 0, 0)
_YELLOW = (255, 255, 0)
_BLUE = (0, 0, 255)
_GREEN = (0, 255, 0)
_PURPLE = (255, 0, 255)
_CYAN = (0, 255, 255)
_PINK = (255, 105, 180)
_ORANGE = (255, 165, 0)

# Color mapping for events
EVENT_COLOR_MAP = {
    "StreamingStarted": _CYAN,
    "NoInternet": _BLUE,
    "Processing": _PINK,
    "VoiceStarted": _YELLOW,
    "Transcript": _WHITE,
    "Starting": _PURPLE,
    "Running": _RED,
    "Connected": _GREEN,
    "Shutdown": _ORANGE,
    "Paused": _ORANGE,
    "Off": _BLACK
}

# Socket configuration
LED_SERVER_HOST = '127.0.0.1'
LED_SERVER_PORT = 8765
LED_SERVER_SOCKET_PATH = '/tmp/led_service.sock'

class LEDServiceClient:
    """Client for the LED service that communicates over a socket."""
    
    def __init__(self):
        self.socket_path = LED_SERVER_SOCKET_PATH
        
    def handle_event(self, event: str) -> None:
        """Send an event to the LED service."""
        try:
            # Check if socket exists, otherwise log and continue
            if not os.path.exists(self.socket_path):
                logger.debug(f"LED service socket not found at {self.socket_path}. LED service may not be running.")
                print(f"LED Event: {event} (service not available)")
                return
            
            # Create socket and send event
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(self.socket_path)
                message = json.dumps({"action": "event", "event": event})
                sock.sendall(message.encode())
                # Optional: Wait for acknowledgement
                response = sock.recv(1024).decode()
                if "error" in response:
                    logger.error(f"Error from LED service: {response}")
        except (socket.error, ConnectionRefusedError) as e:
            logger.error(f"Failed to connect to LED service: {e}")
            print(f"LED Event: {event} (connection failed)")
    
    def blink(self, rgb: Tuple[int, int, int], duration: int = 3, interval: float = 0.3) -> None:
        """Send a blink command to the LED service."""
        try:
            if not os.path.exists(self.socket_path):
                logger.debug(f"LED service socket not found at {self.socket_path}. LED service may not be running.")
                print(f"LED Blink: {rgb} (service not available)")
                return
                
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(self.socket_path)
                message = json.dumps({
                    "action": "blink",
                    "rgb": rgb,
                    "duration": duration,
                    "interval": interval
                })
                sock.sendall(message.encode())
                response = sock.recv(1024).decode()
                if "error" in response:
                    logger.error(f"Error from LED service: {response}")
        except (socket.error, ConnectionRefusedError) as e:
            logger.error(f"Failed to connect to LED service: {e}")
            print(f"LED Blink: {rgb} (connection failed)")

class LEDServiceServer:
    """Server for the LED service that listens on a socket and controls the LEDs."""
    
    def __init__(self, led_brightness: Optional[int] = None):
        self.socket_path = LED_SERVER_SOCKET_PATH
        self.led_brightness = led_brightness or 31
        self.current_color = _BLACK
        self.server_socket = None
        self.is_running = False
        self.led_power = None
        self.leds = None
        
        # Try to initialize hardware
        try:
            self.led_power = gpiozero.LED(LEDS_GPIO, active_high=False)
            self.led_power.on()
            
            self.leds = APA102(num_led=NUM_LEDS, global_brightness=self.led_brightness)
            self.set_color(_BLACK)  # Start with LEDs off
            logger.info("LED hardware initialized successfully")
        except ImportError as e:
            logger.warning(f"LED hardware modules not available: {e}")
            logger.warning("LED control will be simulated")
        except Exception as e:
            logger.error(f"LED initialization error: {e}")
            logger.warning("LED control will be simulated")
    
    def start(self):
        """Start the LED service server."""
        # Remove socket file if it already exists
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
            
        # Create and bind socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        self.server_socket.listen(5)
        
        self.is_running = True
        logger.info(f"LED service server started on {self.socket_path}")
        
        # Start listening thread
        thread = threading.Thread(target=self._listen, daemon=True)
        thread.start()
        
        return thread
    
    def _listen(self):
        """Listen for incoming connections and handle them."""
        while self.is_running:
            try:
                client_socket, _ = self.server_socket.accept()
                thread = threading.Thread(target=self._handle_client, args=(client_socket,), daemon=True)
                thread.start()
            except socket.error as e:
                if self.is_running:  # Only log if not shutting down
                    logger.error(f"Socket error: {e}")
                    time.sleep(0.1)
    
    def _handle_client(self, client_socket):
        """Handle a client connection."""
        try:
            data = client_socket.recv(1024).decode()
            if not data:
                return
                
            try:
                message = json.loads(data)
                action = message.get("action", "")
                
                if action == "event":
                    event = message.get("event", "")
                    self.handle_event(event)
                    client_socket.sendall(json.dumps({"status": "ok"}).encode())
                elif action == "blink":
                    rgb = tuple(message.get("rgb", [0, 0, 0]))
                    duration = message.get("duration", 3)
                    interval = message.get("interval", 0.3)
                    # Run blink in a separate thread so it doesn't block
                    threading.Thread(target=self.blink, args=(rgb, duration, interval), daemon=True).start()
                    client_socket.sendall(json.dumps({"status": "ok"}).encode())
                else:
                    client_socket.sendall(json.dumps({"error": "Unknown action"}).encode())
            except json.JSONDecodeError:
                client_socket.sendall(json.dumps({"error": "Invalid JSON"}).encode())
        except Exception as e:
            logger.error(f"Error handling client: {e}")
            try:
                client_socket.sendall(json.dumps({"error": str(e)}).encode())
            except:
                pass
        finally:
            client_socket.close()
    
    def handle_event(self, event: str) -> None:
        """Handle an event by setting the appropriate LED color."""
        logger.debug(f"Handling event: {event}")
        color = EVENT_COLOR_MAP.get(event, _BLACK)
        self.set_color(color)
    
    def set_color(self, rgb: Tuple[int, int, int]) -> None:
        """Set the LED color."""
        if self.current_color == rgb:
            return
            
        if self.leds is None:
            logger.debug(f"LED Event: {rgb} (simulated)")
            self.current_color = rgb
            return
            
        try:
            for i in range(NUM_LEDS):
                self.leds.set_pixel(i, rgb[0], rgb[1], rgb[2])
            self.leds.show()
            self.current_color = rgb
        except Exception as e:
            logger.error(f"Error setting LED color: {e}")
    
    def blink(self, rgb: Tuple[int, int, int], duration: int = 3, interval: float = 0.3) -> None:
        """Blink the LEDs with the specified color."""
        logger.debug(f"Blinking LEDs: {rgb}, {duration} times, {interval}s interval")
        for _ in range(duration):
            self.set_color(rgb)
            time.sleep(interval)
            self.set_color(_BLACK)
            time.sleep(interval)
    
    def stop(self):
        """Stop the LED service server."""
        logger.info("Stopping LED service server...")
        self.is_running = False
        
        # Turn off LEDs
        self.set_color(_BLACK)
        
        # Clean up hardware
        if self.leds:
            try:
                self.leds.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up LEDs: {e}")
        
        if self.led_power:
            try:
                self.led_power.off()
            except Exception as e:
                logger.error(f"Error turning off LED power: {e}")
        
        # Close socket
        if self.server_socket:
            self.server_socket.close()
        
        # Remove socket file
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        logger.info("LED service server stopped")

# For backwards compatibility
class LEDService:
    """Backwards compatible LED service class.
    
    This class will automatically use the client or server based on how it's used.
    """
    
    def __init__(self, led_brightness=None):
        self.led_brightness = led_brightness
        self.client = LEDServiceClient()
        self._server = None
    
    def handle_event(self, event):
        """Handle an event by sending it to the LED service."""
        self.client.handle_event(event)
    
    def blink(self, rgb, duration=3, interval=0.3):
        """Blink the LEDs by sending a command to the LED service."""
        self.client.blink(rgb, duration, interval)
    
    def start_server(self):
        """Start the LED service server."""
        if self._server is None:
            self._server = LEDServiceServer(self.led_brightness)
            return self._server.start()
        return None
    
    def stop_server(self):
        """Stop the LED service server if it's running."""
        if self._server:
            self._server.stop()
            self._server = None

# Create a default LED service client
led_service = LEDServiceClient()

def run_server():
    """Run the LED service server."""
    server = LEDServiceServer()
    thread = server.start()
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Stopping server...")
    finally:
        server.stop()

if __name__ == "__main__":
    run_server()