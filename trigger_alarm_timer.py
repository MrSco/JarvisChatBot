# trigger_alarm_timer.py
import sys
from datetime import datetime
import time
from sound_effect_service import SoundEffectService
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

def alarm_callback():
    logger.info("Alarm triggered!")
    # Add your alarm handling code here, e.g., play a sound
    sound_effect = SoundEffectService()
    sound_effect.play("alarm")

def timer_callback():
    logger.info("Timer finished!")
    # Add your timer handling code here, e.g., play a sound
    sound_effect = SoundEffectService()
    sound_effect.play("timer")

if __name__ == "__main__":
    action = sys.argv[1]

    if action == "alarm":
        alarm_callback()
    elif action == "timer":
        timer_callback()