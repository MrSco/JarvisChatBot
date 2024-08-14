#!/usr/bin/python
import RPi.GPIO as GPIO
import time
import os
import signal
import sys
from sound_effect_service import SoundEffectService
from led_service import LEDService 

def signal_handler(sig, frame):
    print('Signal received: ', sig)
    # Perform any cleanup here
    print('Exiting gracefully...')
    GPIO.cleanup()
    sys.exit(0)

# Catch SIGINT (Ctrl+C), you can also catch SIGTERM
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
GPIO.setmode(GPIO.BCM)
pin = 17
GPIO.setup(pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
buttonPressTime = None
sound_effect = SoundEffectService()
led_service = LEDService(led_brightness=15)
led_service.handle_event("Starting")
while True:
    #grab the current button state
    buttonState1 = GPIO.input(pin)

    # check to see if button has been pushed
    if buttonState1 == False:
        if buttonPressTime is None:
            # Record the time when the button is pressed
            buttonPressTime = time.time()
        elif time.time() - buttonPressTime >= 5:
            os.system("sudo systemctl stop --now jarvischatbot.service")
            # If the button is held down for 5 seconds, poweroff
            os.system("sudo poweroff")
            # Reset the button press time
            buttonPressTime = None
    else:
        if buttonPressTime is not None:
            # If the button was not held down for 5 seconds, toggle jarvischatbot.service
            if time.time() - buttonPressTime < 5:
                output = os.popen('sudo systemctl is-active jarvischatbot.service').read()
                led_service.turn_on()
                # check if jarvischatbot.service is running and toggle it
                if 'inactive' in output or 'failed' in output:
                    sound_effect.play("halflifebutton")
                    led_service.handle_event("Starting")
                    os.system("sudo systemctl start jarvischatbot.service")        
                else:
                    sound_effect.play("halflifebutton")
                    os.system("sudo systemctl stop --now jarvischatbot.service")
            # Reset the button press time
            buttonPressTime = None
    time.sleep(.1)