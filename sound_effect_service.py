import os
import random
import threading
import time
import sounddevice
import vlc
import platform
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
sounds_dir = os.path.dirname(os.path.abspath(__file__)) + "/sounds"
lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sound_lock")

# Import fcntl if available (Linux/Mac)
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    logger.info("fcntl not available, skipping IPC for sound effects")

class SoundEffectService:
    # Class variable to track all instances
    _instances = []
    
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
        self.tts_engine = config.get("tts_engine", "elevenlabs")
        self.is_looping = False
        self.loop_thread = None
        self.generic_sound_names = ["error", "awake", "done", "initializing", "loading", "halflifebutton", "alarm", "timer"]
        self.awake_sound_names = ["listening", "you_called", "yes", "hello"]
        self.filler_sound_names = ["ummm", "ehhh", "uhhhh", "hmmm"]
        self.start_time = None        
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_list_player_new()
        if self.is_rpi and self.vlc_instance is not None and self.rpi_playback_device != "":
            self.player.get_media_player().audio_output_device_set("alsa", self.rpi_playback_device)
        
        # Add this instance to the class instances list
        SoundEffectService._instances.append(self)
        if HAS_FCNTL:   
            # Create lock file if it doesn't exist
            if not os.path.exists(lock_file):
                with open(lock_file, 'w') as f:
                    f.write('0')
            
    def get_random_wake_sound(self):
        return self.awake_sound_names[random.randint(0, len(self.awake_sound_names) - 1)]
    
    def get_random_filler_sound(self):
        return self.filler_sound_names[random.randint(0, len(self.filler_sound_names) - 1)]

    def get_sound_path(self, sound_name, assistant_name):
        useAssistantSounds = assistant_name if not sound_name in self.generic_sound_names else ''
        usePiperSounds = 'piper' if useAssistantSounds != '' and (self.tts_engine == 'piper' or not os.path.exists(os.path.join(sounds_dir, useAssistantSounds, f"{sound_name}.wav"))) else ''
        return os.path.join(sounds_dir, usePiperSounds, useAssistantSounds, f"{sound_name}.wav")

    def wait_for_sound_to_finish(self):
        # Poll until the media player's state is Ended, Stopped, or Error
        while True:
            state = self.player.get_state()
            if state in [vlc.State.Ended, vlc.State.Stopped, vlc.State.Error]:
                break
            time.sleep(0.1)

    def _play_sound_loop(self):
        """Helper function to play a sound in a loop"""
        self.player.play()
        while self.is_looping:
            time.sleep(0.1)
        end_time = time.time()
        logger.info(f"Sound played in loop for {end_time - self.start_time} seconds")

    def _cleanup_audio(self):
        """Helper function to clean up audio resources"""
        self.is_looping = False
        if self.player is not None:
            self.player.stop()
        if self.loop_thread is not None and self.loop_thread.is_alive():
            self.loop_thread.join()
        self.loop_thread = None

    @classmethod
    def stop_all_sounds(cls):
        """Stop all sounds from all instances of SoundEffectService in this process"""
        logger.info(f"Stopping all sounds from {len(cls._instances)} instances in this process")
        for instance in cls._instances:
            instance.stop_sound()
        
        # Signal other processes to stop sounds
        cls.signal_stop_sounds()

    @classmethod
    def signal_stop_sounds(cls):
        """Signal to all processes to stop sounds"""
        try:
            if HAS_FCNTL:
                with open(lock_file, 'r+') as f:
                    # Get an exclusive lock
                    fcntl.flock(f, fcntl.LOCK_EX)
                    try:
                        counter = int(f.read().strip() or '0')
                        counter += 1
                        f.seek(0)
                        f.truncate()
                        f.write(str(counter))
                        logger.info(f"Signaled stop to all processes: {counter}")
                    finally:
                        # Release the lock
                        fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            logger.error(f"Error signaling sound stop: {e}")

    def check_stop_signal(self):
        """Check if another process has signaled to stop sounds"""
        try:
            last_check = getattr(self, '_last_stop_check', 0)
            
            if HAS_FCNTL:
                with open(lock_file, 'r') as f:
                    # Get a shared lock for reading
                    fcntl.flock(f, fcntl.LOCK_SH)
                    try:
                        counter = int(f.read().strip() or '0')
                        if counter > last_check:
                            self._last_stop_check = counter
                            logger.info(f"Received stop signal from another process: {counter}")
                            return True
                        self._last_stop_check = counter
                    finally:
                        # Release the lock
                        fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            logger.error(f"Error checking stop signal: {e}")
        return False

    def play(self, sound_name, loop=False):
        sound_path = self.get_sound_path(sound_name, self.assistant_name)
        logger.info(f"Playing {'looping' if loop else ''} sound: {sound_path}")
        if not os.path.exists(sound_path):
            raise ValueError(f"Sound '{sound_name}' not found.")
        
        # Clean up any existing audio
        self._check_for_stop_signal()
        self._cleanup_audio()
        
        # Load the sound
        try:
            media_list = self.vlc_instance.media_list_new([vlc.Media(sound_path)])            
            self.player.set_media_list(media_list)
            if loop:
                self.player.set_playback_mode(vlc.PlaybackMode.loop)
                # start a timer so we can see how long the sound is playing for
                self.start_time = time.time()
                self.is_looping = True
                self.loop_thread = threading.Thread(target=self._play_sound_loop)
                self.loop_thread.start()
                
                if HAS_FCNTL:
                    # Start a thread to check for stop signals
                    if not hasattr(self, '_stop_check_thread') or not self._stop_check_thread.is_alive():
                        self._stop_check_thread = threading.Thread(target=self._check_for_stop_signal)
                        self._stop_check_thread.daemon = True
                        self._stop_check_thread.start()
            else:
                self.player.set_playback_mode(vlc.PlaybackMode.default)
                # Play the sound once
                self.player.play()
                self.wait_for_sound_to_finish()
                self.player.stop()
                logger.info("Sound played once")
        except Exception as e:
            logger.error(f"Error playing sound: {e}")
            self._cleanup_audio()
    
    def _check_for_stop_signal(self):
        """Thread that periodically checks for stop signals from other processes"""
        while self.is_looping:
            if self.check_stop_signal():
                logger.info("Stopping sound due to signal from another process")
                self.stop_sound()
                break
            time.sleep(0.5)
    
    def play_loop(self, sound_name):
        self.play(sound_name, loop=True)
        return self

    def stop_sound(self):
        #logger.debug("Stopping sound...")
        self._cleanup_audio()

    def play_from_bytes(self, audio_bytes, loop=False):
        """Play audio from a BytesIO object"""
        # Clean up any existing audio
        self._cleanup_audio()
        
        try:
            # Reset the buffer position
            audio_bytes.seek(0)
            
            # load the audio from bytes into a vlc media player
            media_list = self.vlc_instance.media_list_new([vlc.Media(audio_bytes)])
            self.player.set_media_list(media_list)
            if loop:
                self.is_looping = True
                self.player.set_playback_mode(vlc.PlaybackMode.loop)
                self.loop_thread = threading.Thread(target=self._play_sound_loop)
                self.loop_thread.start()
                if HAS_FCNTL:   
                    # Start a thread to check for stop signals
                    if not hasattr(self, '_stop_check_thread') or not self._stop_check_thread.is_alive():
                        self._stop_check_thread = threading.Thread(target=self._check_for_stop_signal)
                        self._stop_check_thread.daemon = True
                        self._stop_check_thread.start()
            else:
                # Play the sound once
                self.player.set_playback_mode(vlc.PlaybackMode.default)
                self.player.play()
                self.wait_for_sound_to_finish()
                self.player.stop()
                logger.info("Sound played once")
        except Exception as e:
            logger.error(f"Error playing sound from bytes: {e}")
            self._cleanup_audio()