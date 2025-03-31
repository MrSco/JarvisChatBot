import os
import re
import tempfile
import sys
from elevenlabs import VoiceSettings
from elevenlabs import stream, play
from elevenlabs.client import ElevenLabs
import pyttsx3
from gtts import gTTS
import subprocess
import io
from sound_effect_service import SoundEffectService
import logging
import time
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
            self.tts_engine = "pyttsx3"
        self.language = config["language"]
        self.accent = config["assistant_dict"]["accent"]
        self.sound_effect = None
        self.is_running = True
        self.is_rpi = False
        self.rpi_playback_device = config.get("rpi_playback_device", "")
        # Speech rate for pyttsx3 (words per minute, default 200)
        self.speech_rate = config["assistant_dict"].get("speech_rate", 175)
        # Piper TTS settings
        self.piper_voice = config.get("assistant", 'jarvis')
        self.piper_models_dir = "piper_models"

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
                self.speak_with_pyttsx3(text)

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
            
            # Get the current Python executable path (from virtual environment)
            python_exec = sys.executable
            # Quote the path for shell commands to handle spaces properly
            quoted_python_exec = f'"{python_exec}"'
            
            # Check if piper is installed
            try:
                args = [python_exec, '-m', 'piper', '--help']
                if self.is_rpi: # on RPi we use the piper binary directly
                    args = ['piper', '--help']
                subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                has_piper = True
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                # Log the exception details
                logger.error(f"Piper TTS not found - please install it first. Error: {str(e)}")
                self.speak_with_pyttsx3(text)
                return False
            
            # Set up the piper command
            voice_file = os.path.join(
                self.piper_models_dir, 
                f"{self.piper_voice}.onnx"
            )
            # Quote the voice file path to handle spaces
            quoted_voice_file = f'"{voice_file}"'
            json_file = f"{voice_file}.json"
            
            # Check if files exist
            if not os.path.exists(voice_file) or not os.path.exists(json_file):
                logger.error(f"Piper model files not found: {voice_file} or {json_file}")
                self.speak_with_pyttsx3(text)
                return

            # remove any spaces from the start/end of the text
            text = text.strip()
            # First try to use mpv on any platform (including RPi)
            try:
                subprocess.run(['mpv', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                has_mpv = True
            except (subprocess.SubprocessError, FileNotFoundError):
                has_mpv = False
            
            if self.is_rpi:
                # Fallback to aplay on RPi if mpv is not available
                piper_cmd = f"echo \"{text}\" | piper --model {quoted_voice_file} --output-raw"
                # Format for aplay: -D hw:0,0 or -D plughw:CARD=sndrpihifiberry,DEV=0
                play_cmd = ['aplay', '-D', self.rpi_playback_device, '-r', '22050', '-f', 'S16_LE', '-t', 'raw'] if self.rpi_playback_device else ['aplay']
                
                piper_process = subprocess.Popen(piper_cmd, shell=True, stdout=subprocess.PIPE)
                aplay_process = subprocess.Popen(play_cmd, stdin=piper_process.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                piper_process.stdout.close()  # Allow piper to receive a SIGPIPE if aplay exits
                aplay_process.communicate()
                
                # Wait until the sound is finished
                while aplay_process.poll() is None:
                    time.sleep(0.1)
            elif has_mpv:
                # Use Python executable to run piper as a module
                piper_cmd = "piper" if self.is_rpi else f"{quoted_python_exec} -m piper"
                piper_cmd = f"echo \"{text}\" | {piper_cmd} --model {quoted_voice_file}"
                piper_process = subprocess.Popen(piper_cmd, shell=True, stdout=subprocess.PIPE)
                
                # Build mpv command with audio device if on RPi
                mpv_args = ['mpv', '--no-video', '--']
                if self.is_rpi and self.rpi_playback_device:
                    # Format for mpv: --audio-device=alsa/hw:0,0 or alsa/dmix:CARD=sndrpihifiberry,DEV=0
                    mpv_args.insert(1, f'--audio-device=alsa/{self.rpi_playback_device}')
                mpv_args.append('-')

                #print the mpv command we are about to run
                logger.info(f"Running mpv command:  {piper_cmd} | {' '.join(mpv_args)}")
                
                mpv_process = subprocess.Popen(mpv_args, 
                                            stdin=piper_process.stdout, 
                                            stdout=subprocess.DEVNULL, 
                                            stderr=subprocess.DEVNULL)
                piper_process.stdout.close()  # Allow piper to receive a SIGPIPE if mpv exits
                mpv_process.communicate()
                
                # Wait until the sound is finished
                while mpv_process.poll() is None:
                    time.sleep(0.1)
            else:
                # Fallback to temp file on other platforms if mpv is not available
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                    temp_file_name = temp_file.name
                    quoted_temp_file = f'"{temp_file_name}"'
                    piper_cmd = f"echo \"{text}\" | {quoted_python_exec} -m piper --model {quoted_voice_file} --output_file {quoted_temp_file}"
                    logger.info(f"Running piper command: {piper_cmd}")
                    subprocess.run(piper_cmd, shell=True, check=True)
                
                # Create a temporary SoundEffectService instance to play the audio
                temp_sound_service = SoundEffectService()
                temp_sound_service.play(temp_file_name)
                
                # Clean up the temporary file after playing
                time.sleep(0.1)  # Small delay to ensure the file is accessible
                os.remove(temp_file_name)
        except Exception as e:
            logger.error(f"Error playing Piper audio: {e}")
            logger.error(f"Exception type: {type(e).__name__}, Details: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.speak_with_pyttsx3(text)
                
    def speak_with_pyttsx3(self, text):
        try:
            # First stop any sound effects
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            logger.info(f"{self.assistant_name}: {text}")
            if self.is_rpi:
                cmd = f"espeak -s{self.speech_rate} --stdout \"{text}\""
                #logger.debug(f"Speaking with: {cmd}")
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
                #logger.debug(f"Speaking with pyttsx3: {text}")
                engine = pyttsx3.init()
                #logger.debug("Engine initialized")
                # Set the speech rate
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