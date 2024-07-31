import os
from pydub import AudioSegment
from pydub.playback import _play_with_simpleaudio

sounds_dir = os.path.dirname(os.path.abspath(__file__)) + "/sounds"

class SoundEffectService:
    def __init__(self, config=None):
        if config is None:
            config = {"assistant": "jarvis"}
        self.assistant_name = config["assistant"]
        self.sounds = {
            "ready": AudioSegment.from_file(os.path.join(sounds_dir, self.assistant_name, "ready.wav"), format="wav"),
            "goodbye": AudioSegment.from_file(os.path.join(sounds_dir, self.assistant_name, "goodbye.wav"), format="wav"),
            "hi_how_can_i_help": AudioSegment.from_file(os.path.join(sounds_dir, self.assistant_name, "hi_how_can_i_help.wav"), format="wav"),
            "something_went_wrong": AudioSegment.from_file(os.path.join(sounds_dir, self.assistant_name, "something_went_wrong.wav"), format="wav"),
            "the_current_time_is": AudioSegment.from_file(os.path.join(sounds_dir, self.assistant_name, "the_current_time_is.wav"), format="wav"),
            "error": AudioSegment.from_file(os.path.join(sounds_dir, "error.wav"), format="wav"),
            "awake": AudioSegment.from_file(os.path.join(sounds_dir, "awake.wav"), format="wav"),
            "done": AudioSegment.from_file(os.path.join(sounds_dir, "done.wav"), format="wav"),
            "initializing": AudioSegment.from_file(os.path.join(sounds_dir, "initializing.wav"), format="wav"),
            "loading": AudioSegment.from_file(os.path.join(sounds_dir, "loading.mp3"), format="mp3"),
            "halflifebutton": AudioSegment.from_file(os.path.join(sounds_dir, "halflifebutton.wav"), format="wav"),
        }
        self.player = None

    def play(self, sound_name, loop=False):
        sound = self.sounds.get(sound_name)
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

