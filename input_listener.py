import sounddevice
import speech_recognition as sr
import logging
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

class InputListener:
    def __init__(self, config):
        logger.info("Initializing InputListener Recognizer...")
        self.rec = sr.Recognizer()
        #logger.debug("Recognizer initialized")
        #logger.debug("Initializing Microphone...")
        self.mic = sr.Microphone()
        #logger.debug("Microphone initialized")
        self.rec.dynamic_energy_threshold = config["dynamic_energy_threshold"]
        self.rec.energy_threshold = config["vad_threshold"]
        self.timeout = config["timeout"]
        self.phrase_time_limit = config["phrase_time_limit"]
        self.language = config["language"] + "-US"
        self.sound_effect = None
        self.handle_led_event = None

        with self.mic as source:
            logger.info("Adjusting for ambient noise...")
            self.rec.adjust_for_ambient_noise(source, duration=1)
            #logger.debug("Adjusted for ambient noise")

    def listen(self):
        if self.sound_effect is not None:
          self.sound_effect.stop_sound()
        self.audio_data = None
        with self.mic as source:
            try:
                logger.info("Listening for request...")
                self.handle_led_event("Transcript")
                self.audio_data = self.rec.listen(source, timeout = self.timeout, phrase_time_limit = self.phrase_time_limit)
            except Exception:
                pass

    def transcribe(self):
        self.transcript = None
        if self.audio_data is None:
            logger.info("No audio request detected.")
            if self.sound_effect is not None:
                self.sound_effect.stop_sound()
            return None
        try:
            logger.info("Processing speech request to text...")
            self.transcript = self.rec.recognize_google(self.audio_data, language=self.language)
        except sr.UnknownValueError as e:
                # Handle the case where the speech is unintelligible
                logger.error(f"Could not understand audio. {e}")
        except sr.RequestError as e:
            # Handle the case where the request to Google's API failed
            logger.error(f"Could not request results from STT service; {e}")
        if self.sound_effect is not None:
          self.sound_effect.stop_sound()
