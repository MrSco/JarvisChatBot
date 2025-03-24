#!/usr/bin/python
import json
import RPi.GPIO as GPIO
import time
import os
import signal
import sys
import threading
from sound_effect_service import SoundEffectService
import logging
from led_service import LEDServiceServer, LEDServiceClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# Global LED server reference
led_server = None

def signal_handler(sig, frame):
    logger.info(f'Signal received: {sig}')
    # Perform any cleanup here
    logger.info('Exiting gracefully...')
    # Stop LED server
    if led_server:
        led_server.stop()
    GPIO.cleanup()
    sys.exit(0)

# Catch SIGINT (Ctrl+C), you can also catch SIGTERM
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# GPIO setup
GPIO.setmode(GPIO.BCM)
pin = 17
GPIO.setup(pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
buttonPressTime = None

# Load config
script_dir = os.path.dirname(os.path.abspath(__file__))
config_file = os.path.join(script_dir, "config.json")
config = json.load(open(config_file))

# Initialize sound effects with config
sound_effect = SoundEffectService(config)

# Start the LED server
def start_led_server():
    global led_server
    logger.info("Starting LED service server...")
    led_server = LEDServiceServer()
    return led_server.start()

def stop_jarvischatbot():
    os.system("sudo systemctl stop --now jarvischatbot.service")

def start_jarvischatbot():
    os.system("sudo systemctl start jarvischatbot.service")

# Initialize LED service client and server
led_server_thread = start_led_server()
led_service = LEDServiceClient()
logger.info("LED server started successfully")

# Main GPIO button monitoring loop
def monitor_button():
    global buttonPressTime
    logger.info("Starting button monitoring...")
    
    while True:
        #grab the current button state
        buttonState1 = GPIO.input(pin)

        # check to see if button has been pushed
        if buttonState1 == False:
            led_service.handle_event("Processing")  # Show button is pressed
            if buttonPressTime is None:
                # Record the time when the button is pressed
                buttonPressTime = time.time()
            elif time.time() - buttonPressTime >= 5:
                stop_jarvischatbot()
                # If the button is held down for 5 seconds, poweroff
                os.system("sudo poweroff")
                # Reset the button press time
                buttonPressTime = None
        else:
            if buttonPressTime is not None:
                # If the button was not held down for 5 seconds, toggle jarvischatbot.service
                if time.time() - buttonPressTime < 5:
                    output = os.popen('sudo systemctl is-active jarvischatbot.service').read()
                    # check if jarvischatbot.service is running and toggle it
                    logger.info(f"Jarvischatbot service status: {output}")
                    if 'inactive' in output or 'failed' in output:
                        # Delete the lock file at service startup to ensure fresh state
                        lock_file = os.path.join(script_dir, ".sound_lock")
                        if os.path.exists(lock_file):
                            try:
                                os.remove(lock_file)
                                logger.info("Removed old sound lock file")
                            except Exception as e:
                                logger.error(f"Error removing sound lock file: {e}")

                        led_service.handle_event("Starting")
                        sound_effect.play("halflifebutton")
                        sound_effect.play_loop("loading")
                        start_jarvischatbot()
                    else:
                        sound_effect.play("halflifebutton")
                        stop_jarvischatbot()
                        led_service.handle_event("Off")
                # Reset the button press time
                buttonPressTime = None
        time.sleep(.1)

if __name__ == "__main__":
    try:
        # Run the button monitoring in the main thread
        monitor_button()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        stop_jarvischatbot()
        # Clean up resources
        if led_server:
            led_server.stop()
        if sound_effect:
            sound_effect.stop_all_sounds()
        GPIO.cleanup()
        logger.info("Exiting gracefully")