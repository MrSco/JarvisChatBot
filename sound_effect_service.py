import os
import random
import threading
import time
import sounddevice
import vlc
import platform

sounds_dir = os.path.dirname(os.path.abspath(__file__)) + "/sounds"

class SoundEffectService:
    def __init__(self, config=None):
        if config is None:
            config = {"assistant": "jarvis"}
        elif "assistant" not in config:
            config["assistant"] = "jarvis"
        self.is_rpi = False
        try:
            if "linux" in platform.system().lower():
                # Check if we're on RPi
                with open('/proc/cpuinfo', 'r') as f:
                    if 'Raspberry Pi' in f.read():
                        self.is_rpi = True
        except:
            # If error in RPi detection, it's likely not an RPi
            pass
        self.rpi_playback_device = config.get("rpi_playback_device", "")
        self.assistant_name = config["assistant"]
        self.is_looping = False
        self.loop_thread = None
        self.generic_sound_names = ["error", "awake", "done", "initializing", "loading", "halflifebutton", "alarm", "timer"]
        self.awake_sound_names = ["listening", "you_called", "yes", "hello"]
        self.filler_sound_names = ["ummm", "ehhh", "uhhhh", "hmmm"]
        self.vlc_instance = None
        self.vlc_looping_instance = None
        self.player = None
        self.vlc_looping_player = None
        self.start_time = None        

    def _init_vlc_instance(self):
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()
        if self.is_rpi and self.vlc_instance is not None and self.rpi_playback_device != "":
            self.player.audio_output_device_set("alsa", self.rpi_playback_device)

    def _init_vlc_Looping_instance(self):
        self.vlc_looping_instance = vlc.Instance("--input-repeat=-1")
        self.vlc_looping_player = self.vlc_looping_instance.media_player_new()
        if self.is_rpi and self.vlc_looping_instance is not None and self.rpi_playback_device != "":
            self.vlc_looping_player.audio_output_device_set("alsa", self.rpi_playback_device)

    def get_random_wake_sound(self):
        return self.awake_sound_names[random.randint(0, len(self.awake_sound_names) - 1)]
    
    def get_random_filler_sound(self):
        return self.filler_sound_names[random.randint(0, len(self.filler_sound_names) - 1)]

    def get_sound_path(self, sound_name, assistant_name):
        return os.path.join(sounds_dir, assistant_name if not sound_name in self.generic_sound_names else "", f"{sound_name}.wav")

    def _play_sound_loop(self):
        """Helper function to play a sound in a loop"""
        self.vlc_looping_player.play()
        while self.is_looping:
            time.sleep(0.1)
        end_time = time.time()
        print(f"Sound played in loop for {end_time - self.start_time} seconds")

    def _cleanup_audio(self):
        """Helper function to clean up audio resources"""
        self.is_looping = False
        if self.player is not None:
            self.player.stop()
            self.player = None
            self.vlc_instance = None
        if self.loop_thread is not None and self.loop_thread.is_alive():
            self.loop_thread.join()
        self.loop_thread = None
        if self.vlc_looping_player is not None:
            self.vlc_looping_player.stop()
            self.vlc_looping_player = None
            self.vlc_looping_instance = None

    def play(self, sound_name, loop=False):
        sound_path = self.get_sound_path(sound_name, self.assistant_name)
        print(f"Playing {'looping' if loop else ''} sound: {sound_path}")
        if not os.path.exists(sound_path):
            raise ValueError(f"Sound '{sound_name}' not found.")
        
        # Clean up any existing audio
        self._cleanup_audio()
        
        # Load the sound
        try:
            if loop:
                # start a timer so we can see how long the sound is playing for
                self.start_time = time.time()
                self._init_vlc_Looping_instance()
                self.vlc_looping_player.set_media(vlc.Media(sound_path))
                self.is_looping = True
                self.loop_thread = threading.Thread(target=self._play_sound_loop)
                self.loop_thread.start()
            else:
                # Play the sound once
                self._init_vlc_instance()
                self.player.set_media(vlc.Media(sound_path))
                self.player.play()
                # Poll until the media player's state is Ended
                while True:
                    state = self.player.get_state()
                    if state == vlc.State.Ended:
                        break
                    time.sleep(0.1)
                print("Sound played once")
        except Exception as e:
            print(f"Error playing sound: {e}")
            self._cleanup_audio()
    
    def play_loop(self, sound_name):
        self.play(sound_name, loop=True)
        return self

    def stop_sound(self):
        #print("Stopping sound...")
        self._cleanup_audio()

    def play_from_bytes(self, audio_bytes, loop=False):
        """Play audio from a BytesIO object"""
        # Clean up any existing audio
        self._cleanup_audio()
        
        try:
            # Reset the buffer position
            audio_bytes.seek(0)
            
            # load the audio from bytes into a vlc media player
            
            if loop:
                self.is_looping = True
                self._init_vlc_Looping_instance()
                self.vlc_looping_player.set_media(vlc.Media(audio_bytes))
                self.loop_thread = threading.Thread(target=self._play_sound_loop)
                self.loop_thread.start()
            else:
                # Play the sound once
                self._init_vlc_instance()
                self.player.set_media(vlc.Media(audio_bytes))
                self.player.play()
                # Poll until the media player's state is Ended
                while True:
                    state = self.player.get_state()
                    if state == vlc.State.Ended:
                        break
                    time.sleep(0.1)
                print("Sound played once")
        except Exception as e:
            print(f"Error playing sound from bytes: {e}")
            self._cleanup_audio()