import os
import re
import tempfile
from elevenlabs import VoiceSettings
from elevenlabs import stream, play
from elevenlabs.client import ElevenLabs
import pyttsx3
from gtts import gTTS
import subprocess
from sound_effect_service import SoundEffectService
import logging
import time
import platform
import threading
import queue

logger = logging.getLogger(__name__)

class TextToSpeechService:
    def __init__(self, config):
        self.elevenlabs_key = config["elevenlabs_key"]
        self.elevenlabs_client = ElevenLabs(api_key = self.elevenlabs_key)
        self.assistant_name = config["assistant_dict"]["name"]
        self.assistant_gender = 0 if config["assistant_dict"]["gender"] == "male" else 1
        self.elevenlabs_voice_id = config["assistant_dict"]["elevenlabs_voice_id"]
        self.tts_engine = config.get("tts_engine", "pyttsx3")
        if self.elevenlabs_voice_id == "" and self.tts_engine == "elevenlabs":
            self.tts_engine = "piper"
        self.language = config["language"]
        self.accent = config["assistant_dict"]["accent"]
        self.sound_effect = None
        self.is_running = True
        self.is_rpi = platform.system() == "Linux"  # Check if running on RPi
        self.rpi_playback_device = config.get("rpi_playback_device", "")
        # Speech rate for pyttsx3 (words per minute, default 200)
        self.speech_rate = config["assistant_dict"].get("speech_rate", 175)
        # Piper TTS settings
        self.piper_voice = config.get("assistant", 'jarvis')
        self.piper_models_dir = "piper_models"
        # LED service client
        self.led_service = None
        if self.is_rpi:
            from led_service import LEDServiceClient
            self.led_service = LEDServiceClient()
                
        # Piper and MPV processes
        self.piper_process = None
        self.mpv_process = None
        
        # Start appropriate Piper service based on platform
        if self.tts_engine == "piper":
            self._start_piper_binary()
            self._start_mpv_process()

    def handle_led_event(self, event):
        if self.led_service is not None:
            self.led_service.handle_event(event)
        else:
            if event == "Running":
                return
            logger.info(f"LED event: {event}")

    def _start_piper_binary(self):
        """Start the Piper binary process for RPi"""
        try:
            # Get the path to piper binary
            piper_path = os.path.join("./piper", "piper" if self.is_rpi else "piper.exe")
            if not os.path.exists(piper_path):
                logger.info(f"Piper binary not found: {piper_path}")
                return False
            # Get the path to the model
            model_path = os.path.join(self.piper_models_dir, f"{self.piper_voice}.onnx")
            if not os.path.exists(model_path):
                logger.info(f"Piper model file not found: {model_path}")
                return False
            
            # Build the command for the Piper binary
            cmd = [
                piper_path,
                "--model", model_path,
                "--output-raw"  # Use raw output for streaming
            ]
            
            logger.info(f"Starting Piper binary with command: {' '.join(cmd)}")
            
            # Start the Piper process
            self.piper_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            logger.info("Piper process started successfully")
            return True
            
        except Exception as e:
            logger.info(f"Error starting Piper binary: {e}")
            import traceback
            logger.info(f"Traceback: {traceback.format_exc()}")
            return False

    def _start_mpv_process(self):
        """Start the MPV process that will be reused"""
        try:
            if self.piper_process is None:
                logger.info("Cannot start MPV without Piper process")
                return False
                
            mpv_args = [
                'mpv',
                '--no-video',
                '--demuxer=rawaudio',
                '--demuxer-rawaudio-rate=22050',
                '--demuxer-rawaudio-format=s16le',
                '--demuxer-rawaudio-channels=1',
                '--audio-channels=mono',
                '--audio-samplerate=22050',
                '--audio-buffer=0.1',
            ]
            if self.is_rpi:
                mpv_args.append('--ao=alsa')
            mpv_args.append('-')
            
            logger.info("Starting persistent MPV process...")
            self.mpv_process = subprocess.Popen(
                mpv_args,
                stdin=self.piper_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info("MPV process started successfully")
            return True
        except Exception as e:
            logger.info(f"Error starting MPV process: {e}")
            return False

    def _cleanup_piper_binary(self):
        """Clean up the Piper binary process and MPV process"""
        if self.mpv_process:
            try:
                self.mpv_process.terminate()
                self.mpv_process.wait(timeout=2)
                logger.info("MPV process stopped")
            except Exception as e:
                logger.info(f"Error stopping MPV process: {e}")
                try:
                    self.mpv_process.kill()
                except:
                    pass
            self.mpv_process = None
            
        if self.piper_process:
            try:
                self.piper_process.terminate()
                self.piper_process.wait(timeout=2)
                logger.info("Piper binary stopped")
            except Exception as e:
                logger.info(f"Error stopping Piper binary: {e}")
                try:
                    self.piper_process.kill()
                except:
                    pass
            self.piper_process = None

    def remove_non_ascii(self, text):
        return re.sub(r'[^\x00-\x7F]+', '', text)

    def speak(self, text):
        textToSpeak = text
        try:
            # strip out emojis so we don't try to speak them
            textToSpeak = self.remove_non_ascii(text)
            if self.tts_engine == "pyttsx3":
                self.speak_with_pyttsx3(textToSpeak)
                return None
            elif self.tts_engine == "gtts":
                self.speak_with_gtts(textToSpeak)
                return None
            elif self.tts_engine == "piper":
                self.speak_with_piper(textToSpeak)
                return None

            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            logger.info(f"{self.assistant_name}: {text}")
            
            # Use ElevenLabs streaming
            stream(self.speech_stream(textToSpeak))

        except Exception as e:
            logger.info(f"Failed to use {self.tts_engine} for speech ({text}): {e}")
            # Fallback to pyttsx3 if other methods fail
            self.speak_with_pyttsx3(textToSpeak)
            return None
        
    def speech_stream(self, text):
        try:
            # strip out emojis so we don't try to speak them
            response = self.elevenlabs_client.text_to_speech.convert_as_stream(
                text=text,
                voice_id=self.elevenlabs_voice_id,
                optimize_streaming_latency="0",                
                output_format="mp3_44100_128",
                voice_settings=VoiceSettings(
                    stability=0.8,
                    similarity_boost=0.8,
                )
            )
            for chunk in response:
                if not self.is_running:
                    break
                yield chunk

        except Exception as e:
            logger.info(f"Failed to use elevenlabs for speech ({text}): {e}")
            if self.tts_engine == "gtts":
                self.speak_with_gtts(text)
            else:
                self.speak_with_piper(text)

    def speak_with_gtts(self, text):
        try:
            # Create a gTTS object for the current text chunk
            tts = gTTS(text=text, lang=self.language, tld=self.accent, slow=False)
            
            # Save the audio to a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            tts.save(temp_file.name)
            
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            logger.info(f"{self.assistant_name}: {text}")
            
            # Create a temporary SoundEffectService instance to play the audio
            temp_sound_service = SoundEffectService()
            temp_sound_service.play(temp_file.name)
            # Delete the temporary file
            os.remove(temp_file.name)
        except Exception as e:
            logger.info(f"Failed to use gTTS for speech: {e}")
            self._cleanup_audio()

    def mpv_stderr_reader(self, mpv_process, queue, stop_event):
        """Read MPV stderr output in a separate thread"""
        while not stop_event.is_set():
            try:
                line = mpv_process.stderr.readline()
                if not line:
                    time.sleep(0.01)  # Small sleep if no data
                    continue
                
                # Split the line by any status updates (they start with 'A: ')
                parts = line.strip().split('A: ')
                for part in parts:
                    if part:  # Skip empty parts
                        if not part.startswith('A: '):
                            part = 'A: ' + part
                        queue.put(part)
            except Exception as e:
                logger.info(f"Error reading MPV stderr: {e}")
                time.sleep(0.01)

    def speak_with_piper(self, text):
        try:
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            
            logger.info(f"{self.assistant_name}: {text}")
            
            # Use Piper binary
            if not self.piper_process or self.piper_process.poll() is not None:
                if not self._start_piper_binary():
                    raise Exception("Failed to start Piper binary")
                if not self._start_mpv_process():
                    raise Exception("Failed to start MPV process")
            
            try:
                # Set LED to orange to indicate processing
                self.handle_led_event("Processing")
                
                # Send text to piper
                logger.info("Sending text to Piper...")
                self.piper_process.stdin.write(f"{text}\n".encode())
                self.piper_process.stdin.flush()

                # Wait for Piper to finish generating
                while True:
                    line = self.piper_process.stderr.readline().decode()
                    if not line:
                        logger.info("Piper stderr closed unexpectedly")
                        break
                    logger.info(f"Piper: {line.strip()}")
                    if "Real-time factor" in line:
                        logger.info("Found completion signal!")
                        break
                                
                # Set LED back to VoiceStarted (yellow) for playback
                self.handle_led_event("VoiceStarted")

                # Set up MPV stderr reading thread
                mpv_queue = queue.Queue()
                stop_event = threading.Event()
                stderr_thread = threading.Thread(
                    target=self.mpv_stderr_reader,
                    args=(self.mpv_process, mpv_queue, stop_event),
                    daemon=True
                )
                stderr_thread.start()

                # Wait for MPV to finish playing
                logger.info("Waiting for playback to complete...")
                start_time = time.time()
                last_percentage = 0

                try:
                    while True:
                        # Check if we've exceeded timeout (10 seconds)
                        if time.time() - start_time > 10:
                            logger.info("Timeout reached waiting for playback")
                            break
                        
                        try:
                            # Try to get a line from the queue with a timeout
                            line = mpv_queue.get(timeout=0.01)
                            if not line.strip():  # Skip empty lines
                                continue
                            
                            #logger.info(f"MPV stderr: {line}")
                            
                            # parse out percentage from mpv status line
                            if "%)" in line:
                                try:
                                    percentage = int(line.split("(")[1].split(")")[0].split("%")[0].strip())
                                    if percentage > last_percentage:  # Only print if percentage increased
                                        #logger.info(f"Current percentage: {percentage}")
                                        last_percentage = percentage
                                    if percentage > 90:
                                        logger.info("Playback complete")
                                        time.sleep(0.1)
                                        break
                                except (IndexError, ValueError) as e:
                                    logger.info(f"Error parsing percentage: {e}")
                                    continue
                        except queue.Empty:
                            # No output available, continue waiting
                            continue
                        
                        time.sleep(0.01)  # Small sleep to prevent busy waiting
                finally:
                    # Signal the reader thread to stop
                    stop_event.set()
                    # Wait a brief moment for the thread to finish
                    stderr_thread.join(timeout=0.5)

            except BrokenPipeError:
                logger.info("Pipe broken, restarting processes")
                self._cleanup_piper_binary()  # This will also cleanup MPV
                if not self._start_piper_binary():
                    raise Exception("Failed to restart Piper binary")
                if not self._start_mpv_process():
                    raise Exception("Failed to restart MPV process")
                raise  # Re-raise to retry the operation

        except Exception as e:
            logger.info(f"Error with Piper TTS: {e}")
            # If all else fails, use pyttsx3
            self.speak_with_pyttsx3(text)
    
    
    def _play_audio_file(self, file_path):
        """Play an audio file using the appropriate method"""
        try:
            if self.is_rpi and self.rpi_playback_device:
                # Use aplay on RPi with the specified device
                subprocess.run(["aplay", "-D", self.rpi_playback_device, file_path], check=True)
            else:
                # Use mpv on other platforms
                subprocess.run(["mpv", "--no-video", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception as e:
            logger.info(f"Error playing audio file: {e}")
            # Try to use SoundEffectService as fallback
            try:
                temp_sound_service = SoundEffectService()
                temp_sound_service.play(file_path)
            except Exception as e2:
                logger.info(f"Failed to play audio with fallback method: {e2}")
    
    def speak_with_pyttsx3(self, text):
        try:
            # First stop any sound effects
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            logger.info(f"{self.assistant_name}: {text}")
            if self.is_rpi:
                cmd = f"espeak -s{self.speech_rate} --stdout \"{text}\""
                espeak_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
                args = ['aplay', '-D', self.rpi_playback_device]
                if self.rpi_playback_device == "":
                    args = ['aplay']
                aplay_process = subprocess.Popen(args, stdin=espeak_process.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                espeak_process.stdout.close()  # Allow espeak to receive a SIGPIPE if aplay exits
                aplay_process.communicate()
                #wait until the sound is finished
                while aplay_process.poll() is None:
                    time.sleep(0.1)
            else:
                engine = pyttsx3.init()
                engine.setProperty('rate', self.speech_rate)
                voices = engine.getProperty('voices') 
                engine.setProperty('voice', voices[self.assistant_gender].id)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            
                # Clean up pyttsx3
                del engine
            
        except Exception as e:
            logger.info(f"Failed to use pyttsx3: {e}")

    def __del__(self):
        """Clean up resources when the object is destroyed"""
        self._cleanup_piper_binary()