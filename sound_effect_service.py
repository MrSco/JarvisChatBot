import os
import random
import pygame

sounds_dir = os.path.dirname(os.path.abspath(__file__)) + "/sounds"

class SoundEffectService:
    def __init__(self, config=None):
        if config is None:
            config = {"assistant": "jarvis"}
        elif "assistant" not in config:
            config["assistant"] = "jarvis"
        self.assistant_name = config["assistant"]
        self.current_sound = None
        self.generic_sound_names = ["error", "awake", "done", "initializing", "loading", "halflifebutton", "alarm", "timer"]
        self.awake_sound_names = ["listening", "you_called", "yes", "hello"]
        self.filler_sound_names = ["ummm", "ehhh", "uhhhh", "hmmm"]
        pygame.mixer.init()

    def get_random_wake_sound(self):
        return self.awake_sound_names[random.randint(0, len(self.awake_sound_names) - 1)]
    
    def get_random_filler_sound(self):
        return self.filler_sound_names[random.randint(0, len(self.filler_sound_names) - 1)]

    def get_sound_path(self, sound_name, assistant_name):
        return os.path.join(sounds_dir, assistant_name if not sound_name in self.generic_sound_names else "", f"{sound_name}.wav")

    def play(self, sound_name, loop=False):
        sound_path = self.get_sound_path(sound_name, self.assistant_name)
        if not os.path.exists(sound_path):
            raise ValueError(f"Sound '{sound_name}' not found.")
        
        if self.current_sound is not None:
            self.stop_sound()
            
        self.current_sound = pygame.mixer.Sound(sound_path)
        if loop:
            self.current_sound.play(-1)  # -1 means loop indefinitely
        else:
            self.current_sound.play()
            while pygame.mixer.get_busy():
                pygame.time.Clock().tick(10)
    
    def play_loop(self, sound_name):
        self.play(sound_name, loop=True)
        return self

    def stop_sound(self):
        if self.current_sound is not None:
            self.current_sound.stop()
            self.current_sound = None

