import os
import re
import tempfile
from elevenlabs import VoiceSettings
from elevenlabs import stream, play
from elevenlabs.client import ElevenLabs
import pyttsx3
from gtts import gTTS
import subprocess
import requests
from sound_effect_service import SoundEffectService
import logging
import time
import sys
import platform

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
        
        # Piper HTTP server settings (only used on non-RPi)
        self.piper_http_port = config.get("piper_http_port", 5555)
        self.piper_http_host = config.get("piper_http_host", "localhost")
        self.piper_http_url = f"http://{self.piper_http_host}:{self.piper_http_port}"
        self.piper_server_process = None
        
        # Piper binary process (only used on RPi)
        self.piper_process = None
        self.piper_time_between_chunks = config.get("piper_time_between_chunks", 1)
        
        # Start appropriate Piper service based on platform
        if self.tts_engine == "piper":
            if self.is_rpi:
                self._start_piper_binary()
            else:
                self._start_piper_http_server()

    def _start_piper_http_server(self):
        """Start the Piper HTTP server if it's not already running"""
        try:            
            # Check if server is already running
            try:
                # Try to connect to the server
                requests.get(f"{self.piper_http_url}?text=test", timeout=0.5)
                logger.info(f"Piper HTTP server already running at {self.piper_http_url}")
                return True
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                # Server not running, we'll start it
                logger.info("Piper HTTP server not detected, starting it...")
            
            # Get the path to the model
            model_path = os.path.join(os.path.dirname(__file__), self.piper_models_dir, f"{self.piper_voice}.onnx")
            if not os.path.exists(model_path):
                logger.error(f"Piper model file not found: {model_path}")
                return False
            
            # Prepare the command to start the HTTP server
            # we need quotes around the python_exec to handle spaces in the path
            python_exec = f'"{sys.executable}"'
            
            # Build the command
            # change to the python_run directory    
            os.chdir(os.path.join(os.path.dirname(__file__), "piper", "src", "python_run"))
            cmd = [
                python_exec,
                "-m", "piper.http_server",
                "--model", f'"{model_path}"',
                "--host", self.piper_http_host,
                "--port", str(self.piper_http_port)
            ]
            
            logger.info(f"Starting Piper HTTP server with command: {' '.join(cmd)}")
            
            # Start the server as a background process with shell=True to handle Windows permissions
            self.piper_server_process = subprocess.Popen(
                " ".join(cmd),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for the server to start up
            for i in range(10):
                try:
                    requests.get(f"{self.piper_http_url}?text=test", timeout=0.5)
                    logger.info(f"Piper HTTP server started successfully at {self.piper_http_url}")
                    return True
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                    time.sleep(0.5)
            
            logger.error("Failed to start Piper HTTP server")
            return False
            
        except Exception as e:
            logger.error(f"Error starting Piper HTTP server: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def _cleanup_piper_server(self):
        """Stop the Piper HTTP server if we started it"""
        if self.piper_server_process:
            try:
                self.piper_server_process.terminate()
                self.piper_server_process.wait(timeout=5)
                logger.info("Piper HTTP server stopped")
            except Exception as e:
                logger.error(f"Error stopping Piper HTTP server: {e}")
                try:
                    self.piper_server_process.kill()
                except:
                    pass
            self.piper_server_process = None

    def _start_piper_binary(self):
        """Start the Piper binary process for RPi"""
        try:
            # Get the path to piper binary
            piper_path = os.path.join("./piper", "piper")
            if not os.path.exists(piper_path):
                logger.error(f"Piper binary not found: {piper_path}")
                return False
            # Get the path to the model
            model_path = os.path.join(self.piper_models_dir, f"{self.piper_voice}.onnx")
            if not os.path.exists(model_path):
                logger.error(f"Piper model file not found: {model_path}")
                return False
            
            # Build the command for the Piper binary
            cmd = [
                piper_path,
                "--model", model_path,
                "--output-raw"  # Output raw audio data
            ]
            
            logger.info(f"Starting Piper binary with command: {' '.join(cmd)}")
            
            # Start the Piper process
            self.piper_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            logger.info("Piper binary started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting Piper binary: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def _cleanup_piper_binary(self):
        """Clean up the Piper binary process"""
        if self.piper_process:
            try:
                self.piper_process.terminate()
                self.piper_process.wait(timeout=5)
                logger.info("Piper binary stopped")
            except Exception as e:
                logger.error(f"Error stopping Piper binary: {e}")
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
            logger.error(f"Failed to use {self.tts_engine} for speech ({text}): {e}")
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
            logger.error(f"Failed to use elevenlabs for speech ({text}): {e}")
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
            logger.error(f"Failed to use gTTS for speech: {e}")
            self._cleanup_audio()

    def speak_with_piper(self, text):
        try:
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            
            logger.info(f"{self.assistant_name}: {text}")
            
            text = text.strip()
            if not text:
                return
            
            if self.is_rpi:
                # Use Piper binary on RPi
                if not self.piper_process or self.piper_process.poll() is not None:
                    if not self._start_piper_binary():
                        raise Exception("Failed to start Piper binary")
                
                # Start aplay process to receive the audio stream
                aplay_args = ["aplay"]
                if self.rpi_playback_device:
                    aplay_args.extend(["-D", self.rpi_playback_device])
                aplay_args.extend(["-r", "22050", "-f", "S16_LE", "-t", "raw", "-"])
                
                aplay_process = subprocess.Popen(
                    aplay_args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                try:
                    # Send text to Piper and pipe output to aplay
                    self.piper_process.stdin.write(f"{text}\n".encode())
                    self.piper_process.stdin.flush()
                    
                    # Set stdout to non-blocking mode
                    os.set_blocking(self.piper_process.stdout.fileno(), False)
                    
                    # Stream audio data to aplay - this time read EVERYTHING until we're done
                    consecutive_empty_reads = 0
                    max_empty_reads = 5  # After this many empty reads, consider speech complete
                    has_received_data = False  # Flag to ensure we've received at least some data
                    start_time = time.time()
                    max_wait_time = 5.0  # Maximum time to wait for initial data (seconds)
                    
                    while True:
                        try:
                            chunk = self.piper_process.stdout.read(8192)
                            
                            if not chunk:  # No data or EOF
                                consecutive_empty_reads += 1
                                
                                # Check if we've been waiting too long for initial data
                                if not has_received_data and (time.time() - start_time > max_wait_time):
                                    logger.warning(f"No data received from Piper after {max_wait_time} seconds, giving up")
                                    break
                                    
                                if consecutive_empty_reads >= max_empty_reads:
                                    # Only break if we've received some data already
                                    if has_received_data:
                                        logger.info(f"Detected end of speech after {consecutive_empty_reads} empty reads")
                                        break
                                time.sleep(0.05)  # Shorter sleep for more responsive detection
                                continue
                            
                            # We've received some data
                            has_received_data = True
                            consecutive_empty_reads = 0
                            aplay_process.stdin.write(chunk)
                            aplay_process.stdin.flush()
                            
                        except BlockingIOError:
                            consecutive_empty_reads += 1
                            
                            # Check if we've been waiting too long for initial data
                            if not has_received_data and (time.time() - start_time > max_wait_time):
                                logger.warning(f"No data received from Piper after {max_wait_time} seconds, giving up")
                                break
                                
                            if consecutive_empty_reads >= max_empty_reads:
                                # Only break if we've received some data already
                                if has_received_data:
                                    logger.info(f"Detected end of speech after {consecutive_empty_reads} blocking reads")
                                    break
                            time.sleep(0.05)  # Shorter sleep for more responsive detection
                            continue
                
                    # Close stdin and wait for aplay to finish
                    aplay_process.stdin.close()
                    aplay_process.wait()
                    
                except BrokenPipeError:
                    logger.warning("Pipe broken, restarting Piper process")
                    self._cleanup_piper_binary()
                    if not self._start_piper_binary():
                        raise Exception("Failed to restart Piper binary")
                    raise  # Re-raise to retry the operation
                
            else:
                # Use HTTP server on other platforms
                if not self._check_piper_server():
                    if not self._start_piper_http_server():
                        raise Exception("Failed to start Piper HTTP server")
                
                # Start mpv process to receive the audio stream
                mpv_process = subprocess.Popen(
                    ["mpv", "--no-video", "-"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                # Send GET request to Piper HTTP server
                response = requests.get(
                    self.piper_http_url,
                    params={"text": text},
                    stream=True
                )
                
                if response.status_code != 200:
                    logger.error(f"Server returned error: {response.text}")
                    raise Exception(f"HTTP error {response.status_code}")
                
                # Stream the audio data to mpv
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        mpv_process.stdin.write(chunk)
                
                # Close stdin and wait for mpv to finish
                mpv_process.stdin.close()
                mpv_process.wait()
            

        except Exception as e:
            logger.error(f"Error with Piper TTS: {e}")
            # If all else fails, use pyttsx3
            self.speak_with_pyttsx3(text)
    
    def _check_piper_server(self):
        """Check if the Piper HTTP server is running"""
        import requests
        try:
            requests.get(f"{self.piper_http_url}?text=test", timeout=0.5)
            return True
        except:
            return False
    
    def _play_audio_file(self, file_path):
        """Play an audio file using the appropriate method"""
        try:
            if self.is_rpi and self.rpi_playback_device:
                # Use aplay on RPi with the specified device
                subprocess.run(["aplay", "-D", self.rpi_playback_device, file_path], check=True)
            else:
                # Use mpv on other platforms
                subprocess.run(["mpv", "--no-video", file_path], check=True)
        except Exception as e:
            logger.error(f"Error playing audio file: {e}")
            # Try to use SoundEffectService as fallback
            try:
                temp_sound_service = SoundEffectService()
                temp_sound_service.play(file_path)
            except Exception as e2:
                logger.error(f"Failed to play audio with fallback method: {e2}")
    
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
            logger.error(f"Failed to use pyttsx3: {e}")

    def __del__(self):
        """Clean up resources when the object is destroyed"""
        if self.is_rpi and self.piper_process:
            try:
                self.piper_process.terminate()
                self.piper_process.wait(timeout=5)
                logger.info("Piper binary stopped")
            except Exception as e:
                logger.error(f"Error stopping Piper binary: {e}")
                try:
                    self.piper_process.kill()
                except:
                    pass
        elif not self.is_rpi:
            self._cleanup_piper_server()