import vlc
import threading
import time

class RadioPlayer:
    def __init__(self, wakeword_detector):
        self.wakeword_detector = wakeword_detector
        self.player = vlc.MediaPlayer()
        self.thread = None
        self.running = False
        self.stream_url = None

    def start(self, stream_url=None):
        if not self.running:
            if stream_url is None:
                stream_url = self.stream_url
            else:
                self.stream_url = stream_url
            if stream_url is None:
                print("No stream URL provided")
                return
            self.running = True
            self.wakeword_detector.is_awoken = True
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
            print(f"Error playing stream: {e}")
            self.stop()

    def stop(self):
        if self.running:
            self.running = False
            self.wakeword_detector.is_awoken = False
            self.player.stop()
            if self.thread:
                self.thread.join()
                self.thread = None