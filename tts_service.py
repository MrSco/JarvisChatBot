import re
import time
from elevenlabs import VoiceSettings
from elevenlabs import stream, play
from elevenlabs.client import ElevenLabs
import pyttsx3
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play as pyDubPlay
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

    def remove_non_ascii(self, text):
        return re.sub(r'[^\x00-\x7F]+', '', text)

    def stop(self):
        self.is_running = False
        if self.sound_effect is not None:
            self.sound_effect.stop_sound()
    
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
            stream(self.speech_stream(textToSpeak))

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
            #print("Speaking with gTTS...")
            # Create a gTTS object for the current text chunk
            tts = gTTS(text=text, lang=self.language, tld=self.accent, slow=False)
            
            # Save the audio to a BytesIO object
            audio_bytes = io.BytesIO()
            tts.write_to_fp(audio_bytes)
            audio_bytes.seek(0)
            
            # Load the audio with pydub
            audio = AudioSegment.from_file(audio_bytes, format="mp3")
            
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            print(f"{self.assistant_name}: {text}")
            
            # Play the audio
            pyDubPlay(audio)
        except Exception as e:
            print(f"Failed to use gTTS for speech: {e}")

    def speak_with_pyttsx3(self, text):
        try:
            #print("Speaking with pyttsx3...")            
            engine = pyttsx3.init()
            voices = engine.getProperty('voices') 
            engine.setProperty('voice', voices[self.assistant_gender].id)
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            print(f"{self.assistant_name}: {text}")
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"Failed to use pyttsx3: {e}")