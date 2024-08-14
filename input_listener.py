import speech_recognition as sr

class InputListener:
    def __init__(self, config):
        self.rec = sr.Recognizer()
        self.mic = sr.Microphone()
        self.rec.dynamic_energy_threshold = config["dynamic_energy_threshold"]
        self.rec.energy_threshold = config["vad_threshold"]
        self.timeout = config["timeout"]
        self.phrase_time_limit = config["phrase_time_limit"]
        self.language = config["language"] + "-US"
        self.sound_effect = None

        with self.mic as source:
            print("Adjusting for ambient noise...")
            self.rec.adjust_for_ambient_noise(source, duration=1)

    def listen(self):
        if self.sound_effect is not None:
          self.sound_effect.stop_sound()
        self.audio_data = None
        with self.mic as source:
            try:
                print("Listening for request...")                    
                self.audio_data = self.rec.listen(source, timeout = self.timeout, phrase_time_limit = self.phrase_time_limit)
            except Exception:
                pass

    def transcribe(self):
        self.transcript = None
        if self.audio_data is None:
            print("No audio request detected.")
            return None
        try:
            print("Processing speech request to text...")
            self.transcript = self.rec.recognize_google(self.audio_data, language=self.language)
        except sr.UnknownValueError as e:
                # Handle the case where the speech is unintelligible
                print(f"Could not understand audio. {e}")
        except sr.RequestError as e:
            # Handle the case where the request to Google's API failed
            print(f"Could not request results from STT service; {e}")
        if self.sound_effect is not None:
          self.sound_effect.stop_sound()
