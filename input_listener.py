import speech_recognition as sr

class InputListener:
    def __init__(self, config):
        print("Initializing InputListener Recognizer...")
        self.rec = sr.Recognizer()
        print("Recognizer initialized")
        self.mic = None
        self.initialize_mic(config)

    def initialize_mic(self, config):
        if self.mic is not None:
            try:
                self.mic.__exit__(None, None, None)
            except:
                pass
        print("Initializing Microphone...")
        self.mic = sr.Microphone()
        print("Microphone initialized")
        self.rec.dynamic_energy_threshold = config["dynamic_energy_threshold"]
        self.rec.energy_threshold = config["vad_threshold"]
        self.timeout = config["timeout"]
        self.phrase_time_limit = config["phrase_time_limit"]
        self.language = config["language"] + "-US"
        self.sound_effect = None

        with self.mic as source:
            print("Adjusting for ambient noise...")
            self.rec.adjust_for_ambient_noise(source, duration=1)
            print("Adjusted for ambient noise")

    def cleanup(self):
        if self.mic is not None:
            try:
                self.mic.__exit__(None, None, None)
            except:
                pass
            self.mic = None
        self.rec = None
        self.sound_effect = None

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
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
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
