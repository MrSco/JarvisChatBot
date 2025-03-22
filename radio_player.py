import vlc
import threading
import time
import logging
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

class RadioPlayer:
    def __init__(self, wakeword_detector):
        self.wakeword_detector = wakeword_detector
        self.player = vlc.MediaPlayer()
        self.thread = None
        self.running = False
        self.stream_url = None
        self.blink_led_thread = None

    def start(self, stream_url=None):
        if not self.running:
            if stream_url is None:
                stream_url = self.stream_url
            else:
                self.stream_url = stream_url
            if stream_url is None:
                logger.error("No stream URL provided")
                return            
            self.running = True
            self.wakeword_detector.is_awoken = True
            self.blink_led_thread = threading.Thread(target=self.blink_led)
            self.blink_led_thread.start()
            self.player.set_media(vlc.Media(stream_url))
            self.thread = threading.Thread(target=self._play)
            self.thread.start()

    def blink_led(self):
        while self.running:
            self.wakeword_detector.handle_led_event("Paused")
            time.sleep(0.5)
            self.wakeword_detector.handle_led_event("Off")
            time.sleep(0.5)

    def _play(self):
        try:
            self.player.play()
            while self.running:
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error playing stream: {e}")
            self.stop()

    def stop(self):
        if self.running:
            self.running = False
            self.wakeword_detector.is_awoken = False
            self.player.stop()
            if self.blink_led_thread is not None and self.blink_led_thread.is_alive():
                self.blink_led_thread.join()
            if self.thread:
                self.thread.join()
                self.thread = None

    def cleanup(self):
        self.stop()
        self.wakeword_detector = None

    def update_stream_urls(self, radio_stream_url, kids_radio_stream_url):
        """Update the stream URLs for both radio types"""
        self.stream_url = radio_stream_url
        # If currently playing, stop and restart with new URL
        if self.running:
            current_url = self.stream_url
            self.stop()
            self.start(current_url)