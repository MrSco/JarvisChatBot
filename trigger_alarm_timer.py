# trigger_alarm_timer.py
import sys
from datetime import datetime
import time
from sound_effect_service import SoundEffectService

def alarm_callback():
    print("Alarm triggered!")
    # Add your alarm handling code here, e.g., play a sound
    sound_effect = SoundEffectService()
    sound_effect.play("alarm")

def timer_callback():
    print("Timer finished!")
    # Add your timer handling code here, e.g., play a sound
    sound_effect = SoundEffectService()
    sound_effect.play("timer")

if __name__ == "__main__":
    action = sys.argv[1]

    # Add a delay of 5-7 seconds
    time.sleep(7)  # Adjust the value as needed

    if action == "alarm":
        alarm_callback()
    elif action == "timer":
        timer_callback()