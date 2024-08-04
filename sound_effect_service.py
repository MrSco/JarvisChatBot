import os
from pydub import AudioSegment
from pydub.playback import _play_with_simpleaudio

sounds_dir = os.path.dirname(os.path.abspath(__file__)) + "/sounds"

class SoundEffectService:
    def __init__(self, config=None):
        if config is None:
            config = {"assistant": "jarvis"}
        elif "assistant" not in config:
            config["assistant"] = "jarvis"
        self.assistant_name = config["assistant"]
        self.player = None
        self.generic_sound_names = ["error", "awake", "done", "initializing", "loading", "halflifebutton"]

    def get_sound(self, sound_name, assistant_name):
        return AudioSegment.from_file(os.path.join(sounds_dir, assistant_name if not sound_name in self.generic_sound_names else "", f"{sound_name}.wav"), format="wav")

    def play(self, sound_name, loop=False):
        sound = self.get_sound(sound_name, self.assistant_name)
        if sound is None:
            raise ValueError(f"Sound '{sound_name}' not found.")
        if self.player is not None:
            self.stop_sound()
        #print(f"Playing sound effect: {sound_name}")
        sound = sound * (99 if loop else 1)
        self.player = _play_with_simpleaudio(sound)

        if not loop:
            self.player.wait_done()
    
    def play_loop(self, sound_name):
        self.play(sound_name, loop=True)
        return self

    def stop_sound(self):
        #Stops the currently playing sound.
        if self.player is not None:
            #print("Stopping sound effect...")
            self.player.stop()
            self.player = None  # Reset the player

