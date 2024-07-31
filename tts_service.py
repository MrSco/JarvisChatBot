import time
from elevenlabs import VoiceSettings
from elevenlabs import stream
from elevenlabs.client import ElevenLabs
import pyttsx3
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
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
        self.start_time = None
        self.end_time = None

    def speak(self, text):
        self.start_time = time.time()
        try:            
            if not self.use_elevenlabs:
                if self.use_gtts:
                    self.speak_with_gtts(text)
                    return None
                self.speak_with_pyttsx3(text)
                return None
            print("Speaking with elevenlabs...")
            audio = self.elevenlabs_client.generate(
                text=text,
                voice=self.elevenlabs_voice_id,
                model="eleven_multilingual_v2",
                output_format="mp3_44100_128",
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.8,
                ),
                stream=True
            )
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            self.end_time = time.time()
            print(f"Time taken: {self.end_time - self.start_time} seconds")
            print(f"{self.assistant_name}: {text}")
            stream(audio)

        except Exception as e:
            print(f"Failed to use elevenlabs for speech ({text}): {e}")
            if self.use_gtts:
                self.speak_with_gtts(text)
            else:
                self.speak_with_pyttsx3(text)
            return None

    def speak_with_gtts(self, text):
        try:
            print("Speaking with gTTS...")
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
            self.end_time = time.time()
            print(f"Time taken: {self.end_time - self.start_time} seconds")
            print(f"{self.assistant_name}: {text}")
            
            # Play the audio
            play(audio)
        except Exception as e:
            print(f"Failed to use gTTS for speech: {e}")

    def speak_with_pyttsx3(self, text):
        try:
            print("Speaking with pyttsx3...")            
            engine = pyttsx3.init()
            voices = engine.getProperty('voices') 
            engine.setProperty('voice', voices[self.assistant_gender].id)
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            self.end_time = time.time()
            print(f"Time taken: {self.end_time - self.start_time} seconds")
            print(f"{self.assistant_name}: {text}")
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"Failed to use pyttsx3: {e}")