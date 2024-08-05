import time
from typing import Tuple
from apa102 import APA102
import gpiozero

# LED Settings
NUM_LEDS = 3
LEDS_GPIO = 12

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

class LEDService:
    def __init__(self,):
        self.led_power = gpiozero.LED(LEDS_GPIO, active_high=False)
        self.turn_on()

    def set_color(self,  rgb: Tuple[int, int, int]):
        if self.current_color == rgb:
            return
        # get the variable name of the color
        # color_name = [k for k, v in globals().items() if v == rgb][0]
        # if self.leds is None:
        #     print(f"{self.event}: {color_name}")
        #     return
        for i in range(NUM_LEDS):
            self.leds.set_pixel(i, rgb[0], rgb[1], rgb[2])

        self.leds.show()
        self.current_color = rgb

    def handle_event(self, event):
        self.event = event
        if "StreamingStarted" == event:
            self.set_color(_CYAN)
        elif "NoInternet" == event:
            self.set_color(_BLUE)
        elif "Processing" == event:
            self.set_color(_PINK)
        elif "VoiceStarted" == event:
            self.set_color(_YELLOW)
        elif "Transcript" == event:
            self.set_color(_WHITE)
        elif "Starting" == event:
            self.set_color(_PURPLE)
        elif "Running" == event:
            self.set_color(_RED)
        elif "Connected" == event:
            self.set_color(_GREEN)
        elif "Shutdown" == event:
            self.set_color(_ORANGE)
        elif "Paused" == event:
            self.set_color(_ORANGE)
        elif "Off" == event:
            self.set_color(_BLACK)
    
    def turn_on(self):        
        self.led_power.on()
        self.leds = APA102(num_led=NUM_LEDS)
        self.current_color = _BLACK

    def turn_off(self):
        self.handle_event("Off")
        self.leds.cleanup()
        self.led_power.off()

    def blink(self, rgb, duration):
        for _ in range(duration):
            self.set_color(rgb)
            time.sleep(0.3)
            self.set_color(_BLACK)
            time.sleep(0.3)