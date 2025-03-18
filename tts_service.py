import re
from elevenlabs import VoiceSettings
from elevenlabs import stream, play
from elevenlabs.client import ElevenLabs
import pyttsx3
from gtts import gTTS
import pygame
import io

class TextToSpeechService:
    def __init__(self, config):
        self.elevenlabs_key = config["elevenlabs_key"]
        self.elevenlabs_client = ElevenLabs(api_key = self.elevenlabs_key)
        self.assistant_name = config["assistant_dict"]["name"]
        self.assistant_gender = 0 if config["assistant_dict"]["gender"] == "male" else 1
        self.elevenlabs_voice_id = config["assistant_dict"]["elevenlabs_voice_id"]
        self.use_elevenlabs = config["use_elevenlabs"]
        self.use_gtts = config["use_gtts"]
        self.language = config["language"]
        self.accent = config["assistant_dict"]["accent"]
        self.sound_effect = None
        self.is_running = True
        self.current_sound = None
        # Initialize pygame mixer if not already initialized
        if not pygame.mixer.get_init():
            pygame.mixer.init()

    def remove_non_ascii(self, text):
        return re.sub(r'[^\x00-\x7F]+', '', text)

    def _cleanup_audio(self):
        """Helper function to clean up audio resources"""
        if self.current_sound is not None:
            self.current_sound.stop()
        self.current_sound = None
        # Ensure pygame mixer is ready
        if not pygame.mixer.get_init():
            pygame.mixer.init()

    def stop(self):
        self.is_running = False
        if self.sound_effect is not None:
            self.sound_effect.stop_sound()
        self._cleanup_audio()
        # Quit pygame mixer when stopping
        pygame.mixer.quit()
    
    def speak(self, text):
        textToSpeak = text
        try:
            # strip out emojis so we don't try to speak them
            textToSpeak = self.remove_non_ascii(text)
            if not self.use_elevenlabs:
                if self.use_gtts:
                    self.speak_with_gtts(textToSpeak)
                    return None
                self.speak_with_pyttsx3(textToSpeak)
                return None

            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            print(f"{self.assistant_name}: {text}")
            # Ensure pygame mixer is quit before using ElevenLabs
            pygame.mixer.quit()
            stream(self.speech_stream(textToSpeak))
            # Reinitialize pygame mixer after ElevenLabs
            pygame.mixer.init()

        except Exception as e:
            print(f"Failed to use elevenlabs for speech ({text}): {e}")
            if self.use_gtts:
                self.speak_with_gtts(textToSpeak)
            else:
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
            if self.use_gtts:
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
            
            # Clean up any existing audio
            self._cleanup_audio()
            
            # Load and play the sound using pygame
            self.current_sound = pygame.mixer.Sound(audio_bytes)
            self.current_sound.play()
            while pygame.mixer.get_busy():
                pygame.time.wait(100)
            
            # Clean up
            self._cleanup_audio()
                
        except Exception as e:
            print(f"Failed to use gTTS for speech: {e}")
            self._cleanup_audio()

    def speak_with_pyttsx3(self, text):
        try:
            # Ensure pygame mixer is quit before using pyttsx3
            pygame.mixer.quit()
            engine = pyttsx3.init()
            voices = engine.getProperty('voices') 
            engine.setProperty('voice', voices[self.assistant_gender].id)
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            print(f"{self.assistant_name}: {text}")
            engine.say(text)
            engine.runAndWait()
            # Reinitialize pygame mixer after pyttsx3
            pygame.mixer.init()
        except Exception as e:
            print(f"Failed to use pyttsx3: {e}")
            # Try to reinitialize pygame mixer even if there was an error
            pygame.mixer.init()