# alarm_timer_service.py
import threading
import time
from datetime import datetime, timedelta

class AlarmTimerService:
    def __init__(self):
        self.alarms = []
        self.timers = []
        self.lock = threading.Lock()

    def add_alarm(self, alarm_time, callback):
        with self.lock:
            self.alarms.append((alarm_time, callback))
        threading.Thread(target=self._check_alarms).start()

    def add_timer(self, duration, callback):
        timer_time = datetime.now() + timedelta(seconds=duration)
        with self.lock:
            self.timers.append((timer_time, callback))
        threading.Thread(target=self._check_timers).start()

    def _check_alarms(self):
        while True:
            now = datetime.now()
            with self.lock:
                for alarm_time, callback in self.alarms:
                    if now >= alarm_time:
                        callback()
                        self.alarms.remove((alarm_time, callback))
            time.sleep(1)

    def _check_timers(self):
        while True:
            now = datetime.now()
            with self.lock:
                for timer_time, callback in self.timers:
                    if now >= timer_time:
                        callback()
                        self.timers.remove((timer_time, callback))
            time.sleep(1)