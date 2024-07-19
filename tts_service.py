import time
from elevenlabs import VoiceSettings
from elevenlabs import play, stream
from elevenlabs.client import ElevenLabs
import pyttsx3

class TextToSpeechService:
    def __init__(self, config):
        self.output_format = "mp3_44100_128"
        self.elevenlabs_key = config["elevenlabs_key"]
        self.elevenlabs_client = ElevenLabs(api_key = self.elevenlabs_key)
        self.assistant_name = config["assistant_name"]
        self.elevenlabs_voice_id = config["elevenlabs_voice_id"]
        self.sound_effect = None
        self.stream_responses = config["stream_responses"]
        self.use_elevenlabs = config["use_elevenlabs"]

    def speak(self, text, stream_responses=None):
        if not self.use_elevenlabs:
            self.fallback_speak(text)
            return None

        if stream_responses is None:
            stream_responses = self.stream_responses
        try:
            start_time = time.time()
            audio = self.elevenlabs_client.generate(
                text=text,
                voice=self.elevenlabs_voice_id,
                model="eleven_multilingual_v2",
                output_format=self.output_format,
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.8,
                ),
                stream=stream_responses
            )
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            end_time = time.time()
            print(f"Time taken: {end_time - start_time} seconds")
            if stream_responses:
                stream(audio)
            else:
                print(f"{self.assistant_name}: {text}")
                play(audio)
            
        except Exception as e:
            print(f"Failed to generate and/or play audio: {e}")
            self.fallback_speak(text)
            return None
        
    def fallback_speak(self, text):
        try:
            print("Falling back to pyttsx3...")
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            if self.stream_responses:
                print(f"{self.assistant_name}: {text}")
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"Failed to use pyttsx3: {e}")