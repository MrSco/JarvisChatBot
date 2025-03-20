import re
import time
from elevenlabs import VoiceSettings
from elevenlabs import stream, play
from elevenlabs.client import ElevenLabs
import pyttsx3
from gtts import gTTS
import subprocess
import io
from sound_effect_service import SoundEffectService

class TextToSpeechService:
    def __init__(self, config):
        self.elevenlabs_key = config["elevenlabs_key"]
        self.elevenlabs_client = ElevenLabs(api_key = self.elevenlabs_key)
        self.assistant_name = config["assistant_dict"]["name"]
        self.assistant_gender = 0 if config["assistant_dict"]["gender"] == "male" else 1
        self.elevenlabs_voice_id = config["assistant_dict"]["elevenlabs_voice_id"]
        self.tts_engine = config.get("tts_engine", "pyttsx3")
        if self.elevenlabs_voice_id == "":
            self.tts_engine = "pyttsx3"
        self.language = config["language"]
        self.accent = config["assistant_dict"]["accent"]
        self.sound_effect = None
        self.is_running = True
        self.current_sound = None
        self.is_rpi = False
        # Speech rate for pyttsx3 (words per minute, default 200)
        self.speech_rate = config["assistant_dict"].get("speech_rate", 175)
        # Initialize pygame mixer if not already initialized
        SoundEffectService.init_mixer()

    def remove_non_ascii(self, text):
        return re.sub(r'[^\x00-\x7F]+', '', text)

    def _cleanup_audio(self):
        """Helper function to clean up audio resources"""
        if self.current_sound is not None:
            self.current_sound.stop()
        self.current_sound = None
        # Ensure pygame mixer is ready
        SoundEffectService.init_mixer()

    def stop(self):
        self.is_running = False
        if self.sound_effect is not None:
            self.sound_effect.stop_sound()
        self._cleanup_audio()
        # Quit pygame mixer when stopping
        SoundEffectService.quit_mixer()
    
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

            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            print(f"{self.assistant_name}: {text}")
            # Ensure pygame mixer is quit before using ElevenLabs
            SoundEffectService.quit_mixer()
            stream(self.speech_stream(textToSpeak))
            # Reinitialize pygame mixer after ElevenLabs
            SoundEffectService.init_mixer()

        except Exception as e:
            print(f"Failed to use {self.tts_engine} for speech ({text}): {e}")
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
            print(f"Failed to use elevenlabs for speech ({text}): {e}")
            if self.tts_engine == "gtts":
                self.speak_with_gtts(text)
            else:
                self.speak_with_pyttsx3(text)

    def speak_with_gtts(self, text):
        try:
            # Create a gTTS object for the current text chunk
            tts = gTTS(text=text, lang=self.language, tld=self.accent, slow=False)
            
            # Save the audio to a BytesIO object
            audio_bytes = io.BytesIO()
            tts.write_to_fp(audio_bytes)
            audio_bytes.seek(0)
            
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            print(f"{self.assistant_name}: {text}")
            
            # Create a temporary SoundEffectService instance to play the audio
            temp_sound_service = SoundEffectService()
            temp_sound_service.play_from_bytes(audio_bytes)
                
        except Exception as e:
            print(f"Failed to use gTTS for speech: {e}")
            self._cleanup_audio()

    def speak_with_pyttsx3(self, text):
        try:
            # First stop any sound effects
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            
            # Quit pygame mixer
            SoundEffectService.quit_mixer()
            #print("Pygame mixer quit")
            
            print(f"{self.assistant_name}: {text}")
            if self.is_rpi:
                escaped_text = text.replace("'", "'\\''")                
                cmd = f"espeak -s{self.speech_rate} --stdout '{escaped_text}'"
                #print(f"Speaking with: {cmd}")
                espeak_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
                aplay_process = subprocess.Popen(['aplay', '-D', 'playback'], stdin=espeak_process.stdout)
                espeak_process.stdout.close()  # Allow espeak to receive a SIGPIPE if aplay exits
                aplay_process.communicate()
            else:
                #print(f"Speaking with pyttsx3: {text}")
                # Initialize pyttsx3 with a specific driver
                engine = pyttsx3.init()
                #print("Engine initialized")
                # Set the speech rate
                engine.setProperty('rate', self.speech_rate)
                voices = engine.getProperty('voices') 
                engine.setProperty('voice', voices[self.assistant_gender].id)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            
                # Clean up pyttsx3
                del engine
            
            # Wait a moment before reinitializing pygame
            time.sleep(0.1)
            
            # Reinitialize pygame mixer
            SoundEffectService.init_mixer()
            #print("Pygame mixer reinitialized")
            
        except Exception as e:
            print(f"Failed to use pyttsx3: {e}")
            # Try to reinitialize pygame mixer even if there was an error
            SoundEffectService.init_mixer()