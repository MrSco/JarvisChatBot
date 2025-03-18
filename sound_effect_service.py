import os
import random
import pygame
import threading
import time

sounds_dir = os.path.dirname(os.path.abspath(__file__)) + "/sounds"

class SoundEffectService:
    def __init__(self, config=None):
        if config is None:
            config = {"assistant": "jarvis"}
        elif "assistant" not in config:
            config["assistant"] = "jarvis"
        self.assistant_name = config["assistant"]
        self.current_sound = None
        self.is_looping = False
        self.loop_thread = None
        self.generic_sound_names = ["error", "awake", "done", "initializing", "loading", "halflifebutton", "alarm", "timer"]
        self.awake_sound_names = ["listening", "you_called", "yes", "hello"]
        self.filler_sound_names = ["ummm", "ehhh", "uhhhh", "hmmm"]
        # Initialize pygame mixer
        pygame.mixer.init()

    def get_random_wake_sound(self):
        return self.awake_sound_names[random.randint(0, len(self.awake_sound_names) - 1)]
    
    def get_random_filler_sound(self):
        return self.filler_sound_names[random.randint(0, len(self.filler_sound_names) - 1)]

    def get_sound_path(self, sound_name, assistant_name):
        return os.path.join(sounds_dir, assistant_name if not sound_name in self.generic_sound_names else "", f"{sound_name}.wav")

    def _play_sound_loop(self):
        """Helper function to play a sound in a loop"""
        while self.is_looping and self.current_sound is not None:
            self.current_sound.play()
            while pygame.mixer.get_busy() and self.is_looping:
                pygame.time.wait(100)

    def _cleanup_audio(self):
        """Helper function to clean up audio resources"""
        print("Cleaning up audio...")
        self.is_looping = False
        if self.current_sound is not None:
            self.current_sound.stop()
        if self.loop_thread is not None and self.loop_thread.is_alive():
            self.loop_thread.join()
        self.current_sound = None
        self.loop_thread = None

    def play(self, sound_name, loop=False):
        sound_path = self.get_sound_path(sound_name, self.assistant_name)
        if not os.path.exists(sound_path):
            raise ValueError(f"Sound '{sound_name}' not found.")
        
        # Clean up any existing audio
        self._cleanup_audio()
        
        # Load the sound
        self.current_sound = pygame.mixer.Sound(sound_path)
        
        if loop:
            self.is_looping = True
            self.loop_thread = threading.Thread(target=self._play_sound_loop)
            self.loop_thread.start()
        else:
            # Play the sound once
            self.current_sound.play()
            while pygame.mixer.get_busy():
                pygame.time.wait(100)
            self._cleanup_audio()
    
    def play_loop(self, sound_name):
        self.play(sound_name, loop=True)
        return self

    def stop_sound(self):
        print("Stopping sound...")
        self._cleanup_audio()

    def cleanup(self):
        """Clean up the pygame mixer when the service is done"""
        pygame.mixer.quit()