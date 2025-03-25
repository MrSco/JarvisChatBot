import logging
import base64
from datetime import date, datetime
import json
import os
import platform
import re
import signal
import socket
import sys
import time
from typing import Iterable
from chat_gpt_service import ChatGPTService
from input_listener import InputListener
import pvporcupine
from sound_effect_service import SoundEffectService
from tts_service import TextToSpeechService
from alarm_timer_service import AlarmTimerService
import threading
from flask import Flask, jsonify, render_template, send_from_directory, request
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename
import requests
from radio_player import RadioPlayer
from pvrecorder import PvRecorder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)
script_dir = os.path.dirname(os.path.abspath(__file__))
shairport_handler = None
radio_player = None
detector = None
alarm_timer_service = None
app = None
socketio = None
config = None
config_file = None
assistants = None
assistant_name = None
assistant_acronym = None
led_service = None
is_rpi = False
loading_sound = None
file_chunks = {}

def get_local_ip():
    # Use a dummy connection to a remote host.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # The IP address here is not actually contacted; it is only used to determine the local IP.
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"
    finally:
        s.close()
    return local_ip

def is_running_on_raspberry_pi():
    try:
        with open('/proc/cpuinfo', 'r') as cpuinfo:
            for line in cpuinfo:
                if "Raspberry Pi" in line:
                    return True
    except IOError:
        # /proc/cpuinfo is not accessible, not running on Raspberry Pi
        pass
    return False

config_file = os.path.join(script_dir, "config.json")
assistants_file = os.path.join(script_dir, "assistants.json")
logger.info(f"Loading config from {config_file}...")
config = json.load(open(config_file))
logger.info(f"Loading assistants from {assistants_file}...")
assistants = json.load(open(assistants_file))
assistant = assistants[config["assistant"]]
config["old_assistant"] = config["assistant"]
config["assistant_dict"] = assistant
assistant_name = assistant["name"]
assistant_acronym = assistant["acronym"]
vad_threshold = config["vad_threshold"]
print_audio_level = config["print_audio_level"]
max_threshold = config["max_threshold"]
picovoice_key = config["picovoice_key"]

if not os.path.exists("chatlogs"):
    os.makedirs("chatlogs")

led_service = None
led_brightness = min(config["led_brightness"], 5)
# Check if the script is running on rpi
is_rpi= platform.system() == 'Linux' and is_running_on_raspberry_pi()
if is_rpi:
    try:
        import dbus
        from led_service import LEDServiceClient
        led_service = LEDServiceClient()
        logger.info("LED service client initialized")
        led_service.handle_event("Starting")
    except ImportError as e:
        logger.error(f"Error initializing LED service: {e}")
        logger.error("Make sure you're running this on a Raspberry Pi.")
else:
    logger.info("LED event: Starting")

if config["use_frontend"]:
    app = Flask(__name__)
    socketio = SocketIO(app, async_mode='threading')

def getChatFilename(dateStr):    
    chatlog_filename = os.path.join(script_dir, "chatlogs", f"{config['assistant']}_chatlog-{dateStr}.txt")
    return chatlog_filename

# save conversation to a log file 
def append2log(text, noNewLine=False):
    chatlog_filename = getChatFilename(str(date.today()))
    with open(chatlog_filename, "a", encoding='utf-8') as f:
        f.write(text + ("\n" if not noNewLine else ""))
        f.close
    
    if text:
        socketio.emit('update_chat', {'message': text.strip()})

class ShairportSyncHandler:
    def __init__(self, wakeword_detector, radio_player):
        self.wakeword_detector = wakeword_detector
        self.radio_player = radio_player
        self.is_running = True
        self.shairport_active = False
        self.blink_led_thread = None
        self.bus = dbus.SystemBus()
        self.shairport_proxy = self.bus.get_object('org.gnome.ShairportSync', '/org/gnome/ShairportSync')
        self.shairport_interface = dbus.Interface(self.shairport_proxy, 'org.freedesktop.DBus.Properties')
        self.thread = threading.Thread(target=self.check_if_active)
        self.thread.start()

    def check_if_active(self):
        while self.wakeword_detector.is_running and self.is_running:
            try:                
                if self.shairport_interface.Get('org.gnome.ShairportSync', 'Active'):
                    if not self.shairport_active:
                        if self.radio_player is not None and self.radio_player.running:
                            self.radio_player.stop()
                        self.shairport_active = True
                        self.wakeword_detector.is_awoken = self.shairport_active
                        self.blink_led_thread = threading.Thread(target=self.blink_led)
                        self.blink_led_thread.start()
                        logger.info("Pausing chatbot vad...")
                        socketio.emit('music_active', {'status': 'ready'})
                else:
                    if self.shairport_active:
                        self.shairport_active = False
                        self.wakeword_detector.is_awoken = self.shairport_active
                        if self.blink_led_thread is not None and self.blink_led_thread.is_alive():
                            self.blink_led_thread.join()
                        self.wakeword_detector.handle_led_event("Running")
                        logger.info("Resuming chatbot vad...")
                        socketio.emit('music_active', {'status': 'done'})
            except dbus.DBusException as e:
                logger.error(f"Error communicating with Shairport Sync: {e}")
            time.sleep(0.1)

    def blink_led(self):
        while self.is_running and self.shairport_active:
            self.wakeword_detector.handle_led_event("Paused")
            time.sleep(0.5)
            self.wakeword_detector.handle_led_event("Off")
            time.sleep(0.5)

    def cleanup(self):
        logger.info("Cleaning up Shairport Sync handler...")
        self.shairport_active = False
        if self.blink_led_thread is not None and self.blink_led_thread.is_alive():
            self.blink_led_thread.join()
        self.is_running = False
        if self.thread.is_alive():
            self.thread.join()
        self.bus = None
        self.shairport_interface = None
        self.shairport_proxy = None
        self.blink_led_thread = None
        self.thread = None
        self.wakeword_detector = None
        self.radio_player = None
        
class WakeWordDetector:
    def __init__(self):
        self.is_rpi = is_rpi
        self.rpi_audio_device = config.get("rpi_audio_device", "")
        self.tts_engine = config["tts_engine"]
        if assistant.get('elevenlabs_voice_id', "") == "":
            self.tts_engine = "pyttsx3"
        self.chat_gpt_service = ChatGPTService(config)
        # local ip address
        self.chat_gpt_service.host = get_local_ip()
        self.chat_gpt_service.port = config.get("port", 5000)
        self.chat_gpt_service.append2log = append2log
        
        # Get the wake word from the assistant configuration
        assistant_wake_word = assistant["wake_word"].lower()
        
        # Initialize audio objects
        self.porcupine = None
        self.recorder = None
        self.sound_effect = None
        self.speech = None
        self.listener = None
        
        # init porcupine but if key is bad or missing exit and notify user
        # Initialize Porcupine with the selected keyword
        try:
            self._init_porcupine(assistant_wake_word)
            #print(f"Initialized Porcupine with keyword: {assistant_wake_word}")
        except Exception as e:
            logger.error(f"Error initializing Porcupine: {e}")
            logger.error("Please check your Picovoice key and try again.")
            loading_sound.stop_sound()
            self.cleanup()
            sys.exit(1)

        #stop loading sound so we can test ambient noise properly
        logger.info("Stopping loading sound...")
        loading_sound.stop_sound()
        self.listener = InputListener(config)
        self.listener.handle_led_event = self.handle_led_event
        self._init_audio_stream()

        self.language = config["language"]
        self.is_request_processing = False
        self.is_awoken = False
        self.is_running = True
        self.is_updating = False  # New flag to track assistant updates

        self.speech = TextToSpeechService(config)
        self.speech.is_rpi = is_rpi
        self.sound_effect = SoundEffectService(config)
        self.chat_gpt_service.speech = self.speech
        self.chat_gpt_service.handle_led_event = self.handle_led_event

    def _init_porcupine(self, wake_word):
        """Initialize or reinitialize Porcupine with the given wake word"""
        if self.porcupine is not None:
            try:
                self.porcupine.delete()
            except Exception as e:
                logger.error(f"Error deleting old Porcupine instance: {e}")
        
        if wake_word != "jarvis":
            self.porcupine = pvporcupine.create(
                access_key=picovoice_key,
                keyword_paths=[os.path.join(
                    script_dir, 
                    "porcupine_models", 
                    "rpi" if is_rpi else "", 
                    f"{assistant_name.lower()}.ppn"
                )]
            )
        else:
            self.porcupine = pvporcupine.create(
                access_key=picovoice_key,
                keywords=[wake_word]
            )


    def _cleanup_audio_stream(self):
        """Clean up the audio stream"""
        if self.recorder is not None:
            self.recorder.stop()
            self.recorder.delete()
        self.recorder = None

    def _init_audio_stream(self):
        """Initialize the audio stream"""
        self.handle_led_event("Connected")
        self.is_request_processing = False
        if self.recorder is None:
            #logger.debug("Initializing PvRecorder...")
            self.recorder = PvRecorder(
                frame_length=self.porcupine.frame_length,
                device_index=-1  # Use default device
            )        
            #logger.debug("Starting recorder...")
        self.recorder.start()
        if (shairport_handler is not None and shairport_handler.shairport_active) \
            or (radio_player is not None and radio_player.running) and not self.is_awoken:
            self.is_awoken = True
            socketio.emit('music_active', {'status': 'ready'})
            logger.info("Music active. Pausing chatbot vad...")
        else:
            self.is_awoken = False
            #logger.debug("Audio stream initialized")
            time.sleep(0.1)
            socketio.emit('chatbot_ready', {'status': 'ready'})
            logger.info(f"Listening for '{assistant['wake_word']}'...")
    
    def play_or_speak(self, text):
        if self.tts_engine == "pyttsx3":            
            self.speech.speak(text.split(".")[0].replace("_", " "))
        else:
            self.sound_effect.play(text)

    def process_audio(self):
        self.handle_led_event("VoiceStarted")
        if self.recorder is not None:
            self.recorder.stop()
        if assistant.get('elevenlabs_voice_id', "") == "":
            #print("Speaking ready sound...")
            self.speech.speak(f"{assistant_name} ready!")
        else:
            #print("Playing ready sound...")
            self.sound_effect.play("ready")

        if self.recorder is not None:
            self.recorder.start()
            
        logger.info(f"Listening for '{assistant['wake_word']}'...")
        
        while self.is_running:
            try:
                while self.is_running and self.is_awoken:
                    time.sleep(0.1)

                self.handle_led_event("Running")
                
                try:
                    # Skip audio processing if we're updating the assistant
                    if self.is_updating:
                        time.sleep(0.1)
                        continue
                        
                    # Read audio data
                    pcm = self.recorder.read()
                    
                    # Process with Porcupine
                    keyword_index = self.porcupine.process(pcm)
                    
                    if keyword_index >= 0 and not self.is_request_processing:
                        logger.info(f"Wake word detected! Keyword index: {keyword_index}")
                        
                        # Clean up audio stream before using microphone
                        self._cleanup_audio_stream()
                        
                        socketio.emit('awake', {'status': 'ready'})
                        self.handle_led_event("VoiceStarted")
                        self.play_or_speak(self.sound_effect.get_random_wake_sound())
                        socketio.emit('listening_for_prompt', {'status': 'ready'})                        
                        # Listen for command
                        self.listener.listen()
                        self.handle_led_event("StreamingStarted")
                        socketio.emit('prompt_received', {'status': 'ready'})
                        self.listener.sound_effect = self.sound_effect.play_loop("loading")
                        self.listener.transcribe()
                        if self.listener.transcript is None:
                            # Reinitialize audio stream for wake word detection
                            self._init_audio_stream()
                            continue

                        self.process_transcript(self.listener.transcript)                    
                except Exception as e:
                    logger.error(f"Error processing audio: {e}")
                    self.something_went_wrong()
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.something_went_wrong()
                time.sleep(0.1)

    def handle_led_event(self, event):
        if led_service is not None:
            led_service.handle_event(event)
        else:
            if event == "Running":
                return
            logger.info(f"LED event: {event}")

    def something_went_wrong(self):
        if self.listener and self.listener.sound_effect is not None:
            self.listener.sound_effect.stop_sound()
        if self.chat_gpt_service and self.chat_gpt_service.sound_effect is not None:
            self.chat_gpt_service.sound_effect.stop_sound()
        self.sound_effect.play("error")
        self.play_or_speak("something_went_wrong")
        self._cleanup_audio_stream()
        
    def extract_time_from_transcript(self, transcript):
        # Regular expression to match time in HH:MM AM/PM or HH:MM a.m./p.m. format
        time_pattern = re.compile(r'(\d{1,2}:\d{2}\s?(?:AM|PM|am|pm|a\.m\.|p\.m\.)?)')
        match = time_pattern.search(transcript)
        if match:
            time_str = match.group(1)
            # Normalize the time string to a standard format
            time_str = time_str.replace('.', '').upper()
            # Convert the matched time string to a datetime object
            alarm_time = datetime.strptime(time_str, '%I:%M %p')
            return alarm_time
        else:
            raise ValueError("No valid time found in transcript")

    def extract_duration_from_transcript(self, transcript):
        # Regular expression to match duration in format: 1 second, 2 minutes, 3 hours. 
        # or 1 minute 30 seconds. 
        # or 2 hours and 30 minutes. etc.
        duration_pattern = re.compile(r'(\d+)\s?(second|minute|hour)s?(?:\s+and\s+(\d+)\s?(second|minute|hour)s?)?')
        matches = duration_pattern.findall(transcript)
        total_duration_seconds = 0

        for match in matches:
            for i in range(0, len(match), 2):
                if match[i]:
                    duration_value = int(match[i])
                    duration_unit = match[i + 1].lower()
                    if 'day' in duration_unit:
                        total_duration_seconds += duration_value * 24 * 3600
                    elif 'hour' in duration_unit:
                        total_duration_seconds += duration_value * 3600
                    elif 'minute' in duration_unit:
                        total_duration_seconds += duration_value * 60
                    else:
                        total_duration_seconds += duration_value

        if total_duration_seconds > 0:
            return total_duration_seconds
        else:
            raise ValueError("No valid duration found in transcript")
        
    def durationSecondsToMaxUnits(self, seconds):
        days = seconds // (24 * 3600)
        seconds = seconds % (24 * 3600)
        hours = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        return days, hours, minutes, seconds
    
    def process_transcript(self, transcript, image=None, image_name=''):
        if self.is_request_processing:
            logger.info("A request is already being processed. Please wait.")
            return 
        self.handle_led_event("Processing")
        self.is_request_processing = True
        try:
            start_time = time.time()
            cancel_phrases = [
                "stop",
                "cancel",
                "nevermind",
            ]
            # if transcript starts or ends with any of the cancel phrases, and doesn't have "execution or duneweaver" in the transcript, stop processing
            if any(transcript.lower().startswith(phrase) or transcript.lower().endswith(phrase) for phrase in cancel_phrases) and "execution" not in transcript.lower() and "duneweaver" not in transcript.lower():
                logger.info("Cancel Phrase detected. Cancelling processing...")
                self.sound_effect.play("error")
                return
            logger.info(f"You: {transcript}")
            append2log("")
            # if the user's question is none or too short, skip 
            if len(transcript) < 2 and not image:
                self.handle_led_event("VoiceStarted")
                short_response = "Hi, there, how can I help?"
                self.play_or_speak(self.sound_effect.get_random_filler_sound())
                self.play_or_speak("hi_how_can_i_help")
                append2log(f"You: {transcript} \n")
                append2log(f"{assistant_name}: {short_response} \n")
                return
            
            time_phrases = [
                "what time is it",
                "what is the time",
                "what is the current time",
                "what's the time",
                "what's the current time",
                "do you have the time",
                "do you have the current time",
                "do you know the time",
                "do you know the current time",
                "tell me the time",
                "tell me the current time",
                "tell me what time it is",
            ]

            if any(phrase in transcript for phrase in time_phrases) and "in" not in transcript and not image:
                append2log(f"You: {transcript} \n")
                self.handle_led_event("VoiceStarted")
                self.play_or_speak(self.sound_effect.get_random_filler_sound())
                # get the current time in am/pm format without leading zeros
                current_time = time.strftime('%I:%M %p').lstrip("0").replace("AM", "a.m.").replace("PM", "p.m.")
                response = f"{current_time}"
                append2log(f"{assistant_name}: {response} \n")
                self.speech.speak(response)
                return

            radio_phrases = [
                "play radio",
                "play music",
                "play some music",
                "play some radio",
                "play some tunes",
                "play some songs",
                "play the radio",
                "play the music",
                "play the tunes",
                "play the songs",
            ]

            if any(phrase in transcript.lower() for phrase in radio_phrases) and not image:
                self.handle_led_event("VoiceStarted")
                logger.info("Starting radio...")
                append2log(f"You: {transcript} \n")
                self.play_or_speak(self.sound_effect.get_random_filler_sound())
                radio_player.start(config["radio_stream_url"])
                response = "Radio started."
                append2log(f"{assistant_name}: {response} \n")
                return
            
            radio_phrases = [
                "play kids radio",
                "play kids music",
                "play kids songs",
                "play kids tunes",
                "play kid radio",
                "play kid music",
                "play kid songs",
                "play kid tunes",
                "play the kids radio",
                "play the kids music",
                "play the kids songs",
                "play the kids tunes",
                "play the kid radio",
                "play the kid music",
                "play the kid songs",
                "play the kid tunes",
                "play children's radio",
                "play children's music",
                "play children's songs",
                "play children's tunes",
                "play the children's radio",
                "play the children's music",
                "play the children's songs",
                "play the children's tunes",
            ]

            if any(phrase in transcript.lower() for phrase in radio_phrases) and not image:
                self.handle_led_event("VoiceStarted")
                logger.info("Starting kids radio...")
                append2log(f"You: {transcript} \n")
                self.play_or_speak(self.sound_effect.get_random_filler_sound())
                radio_player.start(config["kids_radio_stream_url"])
                response = "Kids radio started."
                append2log(f"{assistant_name}: {response} \n")
                return

            radio_phrases = [
                "stop playing",
                "stop the radio",
                "stop the music",
                "stop the tunes",
                "stop the songs",
                "stop music",
                "stop radio",
                "stop tunes",
                "stop songs",
                "stop playing music",
                "stop playing radio",
                "stop playing tunes",
                "stop playing songs",
            ]

            if any(phrase in transcript.lower() for phrase in radio_phrases) and not image:
                self.handle_led_event("VoiceStarted")
                logger.info("Stopping radio...")
                append2log(f"You: {transcript} \n")
                self.play_or_speak(self.sound_effect.get_random_filler_sound())
                radio_player.stop()
                response = "Radio stopped."
                append2log(f"{assistant_name}: {response} \n")
                self.speech.speak(response)
                return

            alarm_phrases = [
                "set an alarm",
                "set a alarm",
                "set alarm",
                "set the alarm",
                "wake me up",
            ]

            if any(phrase in transcript.lower() for phrase in alarm_phrases) and not image:
                self.handle_led_event("VoiceStarted")
                logger.info("Setting an alarm...")
                append2log(f"You: {transcript} \n")
                self.play_or_speak(self.sound_effect.get_random_filler_sound())
                # Extract time from transcript and set alarm
                alarm_time = self.extract_time_from_transcript(transcript)
                alarm_timer_service.add_alarm(alarm_time)
                response = "Alarm set for " + alarm_time.strftime('%I:%M %p')
                append2log(f"{assistant_name}: {response} \n")
                self.speech.speak(response)
                return
            
            timer_phrases = [
                "set a timer",
                "set timer",
                "set the timer",
            ]

            if any(phrase in transcript.lower() for phrase in timer_phrases) and not image:
                self.handle_led_event("VoiceStarted")
                logger.info("Setting a timer...")
                append2log(f"You: {transcript} \n")
                self.play_or_speak(self.sound_effect.get_random_filler_sound())
                # Extract duration from transcript and set timer
                duration = self.extract_duration_from_transcript(transcript)
                alarm_timer_service.add_timer(duration)
                days, hours, minutes, seconds = self.durationSecondsToMaxUnits(duration)
                day = f"{days} day" + ("s" if days > 1 else "") + ", " if days else ""
                hour = f"{hours} hour" + ("s" if hours > 1 else "") + ", " if hours else ""
                minute = f"{minutes} minute" + ("s" if minutes > 1 else "") + ", " if minutes else ""
                second = f"{seconds} second" + ("s" if seconds > 1 else "") + ", " if seconds else ""
                response = "Timer set for " + f"{day}{hour}{minute}{second}"
                append2log(f"{assistant_name}: {response} \n")
                self.speech.speak(response)
                return

            delete_phrases = [
            "delete all alarm",
            "reset all alarm",
            "turn off all alarm",
            "cancel all alarm",
            "clear all alarm",
            "forget all alarm",
            "delete alarm",
            "reset alarm",
            "turn off alarm",
            "cancel alarm",
            "clear alarm",
            "forget alarm",
            ]
            if any(phrase in transcript.lower() for phrase in delete_phrases) and not image:
                self.handle_led_event("VoiceStarted")
                self.play_or_speak(self.sound_effect.get_random_filler_sound())
                alarm_timer_service.delete_all_jobs("alarm")
                response = "All alarms and timers deleted"
                append2log(f"{assistant_name}: {response} \n")
                self.speech.speak(response)
                return
            
            delete_phrases = [
            "delete all timer",
            "reset all timer",
            "turn off all timer",
            "cancel all timer",
            "clear all timer",
            "forget all timer",
            "delete timer",
            "reset timer",
            "turn off timer",
            "cancel timer",
            "clear timer",
            "forget timer",
            ]
            if any(phrase in transcript.lower() for phrase in delete_phrases) and not image:
                self.handle_led_event("VoiceStarted")
                self.play_or_speak(self.sound_effect.get_random_filler_sound())
                alarm_timer_service.delete_all_jobs("timer")
                response = "All alarms and timers deleted"
                append2log(f"{assistant_name}: {response} \n")
                self.speech.speak(response)
                return
            
            change_assistant_phrases = [
                "change assistant",
                "switch assistant",
                "change the assistant",
                "switch the assistant",
                "change voice assistant",
                "switch voice assistant",
                "change the voice assistant",
                "switch the voice assistant",
                "change the voice",
                "switch the voice",
                "change voice",
                "switch voice",
                "change your voice",
                "switch your voice",
                "change your name",
                "switch your name",
            ]

            if any(phrase in transcript.lower() for phrase in change_assistant_phrases) and not image:
                self.handle_led_event("VoiceStarted")
                logger.info("Changing assistant...")
                if "taurus" in transcript.lower():
                    logger.info("Handling mispronunciation of Taurus for TARS...")
                    transcript = transcript.replace("Taurus", "taurus").replace("taurus", "Taurus (TARS)")
                append2log(f"You: {transcript} \n")
                # grab the assisant name from the transcript
                new_assistant = next((assistant for assistant in assistants if assistants.get(assistant, {}).get('name', '').lower() in transcript.lower()), None)
                new_assistant_name = assistants.get(new_assistant, {}).get('name', '')
                if new_assistant and new_assistant_name != assistant_name:
                    logger.info(f"Switching to {new_assistant_name}...")
                    change_assistant({'assistant': new_assistant_name.lower()})
                elif new_assistant_name == assistant_name:
                    response = f"I'm already {assistant_name}."
                    logger.info(response)
                    append2log(f"{assistant_name}: {response} \n")
                    self.speech.speak(response)
                else:
                    response = "Assistant not found."
                    logger.info(response)
                    append2log(f"{assistant_name}: {response} \n")
                    self.speech.speak(response)
                return

            self.play_or_speak(self.sound_effect.get_random_filler_sound())            
            append2log(f"You: {transcript}", noNewLine=True)
            self.chat_gpt_service.sound_effect = self.sound_effect.play_loop("loading")
            self.speech.sound_effect = self.chat_gpt_service.sound_effect

            text_iterator = self.chat_gpt_service.send_to_chat_gpt(transcript, image, image_name)
            if text_iterator is None:
                append2log(f"{assistant_name}: Something went wrong.")
                self.something_went_wrong()
                return

            socketio.emit('chat_response_ready', {'status': 'ready'})
            self.handle_led_event("VoiceStarted")
            if isinstance(text_iterator, str):
                text_iterator = [text_iterator]
            elif isinstance(text_iterator, Iterable):
                text_iterator = text_iterator
            else:
                raise ValueError("Invalid input type: text_input must be a string or an iterable")
            for text in text_iterator:
                if text.strip():
                    self.speech.speak(text)
            end_time = time.time()

            logger.info(f"Total Time: {end_time - start_time} seconds")
        finally:
            self._init_audio_stream()

    def run(self):
        try:            
            self.process_audio()
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

    def cleanup(self):
        #print("Cleaning up detector...")
        self.is_running = False
            
        self._cleanup_audio_stream()
                
        if self.porcupine is not None:
            try:
                self.porcupine.delete()
            except Exception as e:
                logger.error(f"Error deleting Porcupine: {e}")
            
        # Reset all references
        self.porcupine = None
        self.speech = None
        self.sound_effect = None
        self.chat_gpt_service = None
        self.listener = None
        self.is_awoken = False
        self.is_request_processing = False

@app.template_filter('find_url')
def find_url_filter(text):
    pattern = re.compile(r'(https?:\/\/[^\s]+\.(jpg|jpeg|png|gif))')
    #grab the first url found in the text
    url = pattern.search(text)[0] if pattern.search(text) else None
    return url if url else None

# Function to get chat logs for a specific date
def get_chat_log_for_date(dateStr):
    chatlog_filename = getChatFilename(dateStr)
    filename = chatlog_filename.split("-")[0] + f"-{dateStr}.txt"
    logger.info(f"Getting chat log for {filename}...")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            # read a line until you reach the end or You: or assistant_name:
            chatlog = []
            for line in f:
                if line.startswith("You: ") or line.startswith(f"{assistant_name}: "):
                    chatlog.append(line)
                else:
                    if chatlog:
                        chatlog[-1] += line
                    else:
                        chatlog.append(line)
    except FileNotFoundError:
        chatlog = []

    chatlog = [{"message": message.strip()} for message in chatlog]
    return chatlog

# @app.route('/set_alarm', methods=['POST'])
# def set_alarm():
#     data = request.json
#     alarm_time = datetime.strptime(data['time'], '%Y-%m-%d %H:%M:%S')
#     alarm_timer_service.add_alarm(alarm_time, alarm_callback)
#     return jsonify({'status': 'alarm set'})

# @app.route('/set_timer', methods=['POST'])
# def set_timer():
#     data = request.json
#     duration = int(data['duration'])
#     alarm_timer_service.add_timer(duration, timer_callback)
#     return jsonify({'status': 'timer set'})

# @app.route('/delete_all_jobs', methods=['POST'])
# def delete_all_jobs():
#     alarm_timer_service.delete_all_jobs()
#     return jsonify({'status': 'all jobs deleted'})

@app.route('/chatlog/<date>', methods=['GET'])
def chatlog(date):
    chatlog = get_chat_log_for_date(date)
    return jsonify(chatlog)

@app.route('/')
def index():
    today = str(date.today())
    chatlog = get_chat_log_for_date(today)
    return render_template('index.html',
                           assistants=assistants, 
                           assistant_dict=assistant, 
                           chatlog=json.dumps(chatlog), 
                           radio_playing=(radio_player is not None and radio_player.running)
                           )

@socketio.on("file_chunk")
def handle_file_chunk(data):
    socketio.emit('prompt_received', {'status': 'ready'})
    detector = app.config['detector']
    # Extracting the chunk data
    file_id = data.get("fileId")
    chunk_index = data.get("chunkIndex") or 0
    total_chunks = data.get("totalChunks") or 0

    chunk_data = base64.b64decode(data.get("chunkData")) if data.get("chunkData") else None
    file_name = secure_filename(data.get("fileName")) if data.get("fileName") else None
    text_prompt = data.get("prompt") if data.get("prompt") else ""
    if file_id:
        logger.info(f"Received chunk {chunk_index + 1} of {total_chunks} for file {file_id}")
        # Initialize the file's chunk list if not already
        if file_id not in file_chunks:
            file_chunks[file_id] = [None] * total_chunks

        # Store the chunk data
        file_chunks[file_id][chunk_index] = chunk_data

        # Check if all chunks have been received
        if all(chunk is not None for chunk in file_chunks[file_id]):
            logger.info(f"Received all chunks for file {file_id}.")
            # Combine binary chunks
            file_data = b"".join(file_chunks[file_id])
            
            if config["image_storage"] == "freeimage" and not config["ai_service"] == "google":
                detector.is_awoken = True
                response = detector.process_transcript(text_prompt, file_data, file_name)
            else:
                upload_path = os.path.join(script_dir, config['upload_folder'])
                if not os.path.exists(upload_path):
                    os.makedirs(upload_path)

                filename = f"{time.time()}_{os.path.basename(file_name)}"
                safe_file_name = os.path.join(upload_path, filename)
                with open(safe_file_name, "wb") as file:
                    file.write(file_data)
                
                file_url = f"http://{detector.chat_gpt_service.host}:{detector.chat_gpt_service.port}/{config['upload_folder']}/{filename}"
                detector.is_awoken = True
                response = detector.process_transcript(text_prompt, file_data, file_url)

            # Delete the chunks from memory
            del file_chunks[file_id]
    else:
        detector.is_awoken = True
        response = detector.process_transcript(text_prompt)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(config['upload_folder'], filename)

@app.route('/history')
def history():
    today = str(date.today())
    chatlog = get_chat_log_for_date(today)
    return render_template('history.html', assistant_dict=assistant, chatlog=json.dumps(chatlog))

def update_configuration(settings_data=None, new_assistant_name=None):
    """Update configuration and services with new settings and/or assistant
    
    Args:
        settings_data (dict, optional): New settings to apply
        new_assistant_name (str, optional): Name of new assistant to switch to
    """
    global config, assistant_name, assistant_acronym, assistant, chatlog_filename, detector, radio_player, alarm_timer_service, led_service
    
    try:
        config_updated = False
        # Update config with new settings if provided
        if settings_data:
            logger.info(f"Updating settings with: {settings_data}")
            for key, value in settings_data.items():
                config[key] = value if key not in ["vad_threshold", "max_threshold", "led_brightness"] else int(value)
            config_updated = True

        # Update assistant if new one specified
        if new_assistant_name and new_assistant_name in assistants:
            logger.info(f"Changing assistant to {new_assistant_name}")
            old_assistant = config['assistant']
            config['assistant'] = new_assistant_name
            config["old_assistant"] = old_assistant
            config["assistant_dict"] = assistants[new_assistant_name]
            assistant = assistants[new_assistant_name]
            assistant_name = assistant["name"]
            assistant_acronym = assistant["acronym"]
            chatlog_filename = getChatFilename(str(date.today()))
            config_updated = True
            logger.info(f"Assistant changed from {old_assistant} to {new_assistant_name}")
        
        if config_updated:
            # Save updated config
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=4)
            logger.info("Settings saved to config.json")

        # Update services with new configuration
        logger.info("Updating services with new configuration...")
        
        # Update LED service if brightness changed
        if is_rpi and led_service is not None:
            led_service.led_brightness = min(config["led_brightness"], 8)
            #print(f"LED brightness updated to {led_service.led_brightness}")
        
        # Update detector services if it exists
        if detector is not None:
            detector.is_updating = True
            detector.tts_engine = config["tts_engine"]
            if assistant.get('elevenlabs_voice_id', "") == "":
                detector.tts_engine = "pyttsx3"
            try:
                detector._cleanup_audio_stream()
                #print("Audio stream cleaned up")
                
                # Update Porcupine if needed
                if new_assistant_name or (settings_data and "picovoice_key" in settings_data):
                    detector._init_porcupine(assistant["wake_word"].lower())
                    #print("Porcupine updated")
                
                # Update other detector services
                detector.listener = InputListener(config)
                #print("Input listener updated")
                detector._init_audio_stream()
                #print("Audio stream reinitialized")
                detector.speech = TextToSpeechService(config)
                detector.speech.is_rpi = is_rpi
                #print("TTS service updated")
                detector.sound_effect = SoundEffectService(config)
                #print("Sound effect service updated")
                detector.chat_gpt_service = ChatGPTService(config)
                # get machine name from os and append .local for local network resolution
                detector.chat_gpt_service.host = f"{socket.gethostname()}.local"
                detector.chat_gpt_service.port = config.get("port", 5000)
                #print("ChatGPT service updated")
                detector.chat_gpt_service.append2log = append2log
                detector.chat_gpt_service.speech = detector.speech
                detector.chat_gpt_service.handle_led_event = detector.handle_led_event
                #print("append2log updated")        
                
                # Reset state
                #print("Resetting state...")
                detector.is_awoken = False
                detector.is_request_processing = False
                #print("State reset")
                if new_assistant_name:
                    #print("Playing ready sound...")
                    if assistant.get('elevenlabs_voice_id', "") == "":
                        #print("Speaking ready sound...")
                        detector.speech.speak(f"{assistant_name} ready!")
                    else:
                        #print("Playing ready sound...")
                        detector.sound_effect.play("ready")
                    #print("Ready sound played")
            finally:
                detector.is_updating = False
        
        # Update radio player URLs if it exists
        if radio_player is not None:
            radio_player.update_stream_urls(config["radio_stream_url"], config["kids_radio_stream_url"])
            #print("Radio player updated")
            
        return True
            
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        return False

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global config
    if request.method == 'POST':
        logger.info(f"Updating settings... with new settings {request.form}")
        if update_configuration(settings_data=request.form):
            return jsonify({"status": "ok"}), 200
        return jsonify({"status": "error"}), 500
    return render_template('settings.html', config=config)

@app.route('/play_radio', methods=['POST'])
def play_radio():
    global radio_player
    if radio_player:
        data = request.get_json()
        logger.info(f"Received data: {data}")
        if data and data.get('radio') == 'kid':
            stream_url = config["kids_radio_stream_url"]
        else:
            stream_url = config["radio_stream_url"]
        radio_player.start(stream_url)
        if radio_player.running:
            return jsonify({"status": "done"}), 200
    return jsonify({"status": "error"}), 500

@app.route('/stop_radio', methods=['POST'])
def stop_radio():
    global radio_player
    if radio_player:
        radio_player.stop()
        if not radio_player.running:
            return jsonify({"status": "done"}), 200
    return jsonify({"status": "error"}), 500

@socketio.on('change_assistant')
def change_assistant(data):
    new_assistant = data.get('assistant')
    if new_assistant and new_assistant in assistants:
        if update_configuration(new_assistant_name=new_assistant):
            socketio.emit('assistant_changed', {'assistant': new_assistant})
            return
    socketio.emit('assistant_changed', {'assistant': None})

def run_flask_app():
    socketio.run(app, debug=False, use_reloader=False, allow_unsafe_werkzeug=True, host="0.0.0.0", port=config.get("port", 5000))

def runApp():
    global detector, shairport_handler, radio_player, alarm_timer_service, loading_sound
    logger.info("Signaling to stop all sounds from other processes...")
    SoundEffectService.stop_all_sounds()
    loading_sound = SoundEffectService(config).play_loop("loading")
    detector = WakeWordDetector()
    radio_player = RadioPlayer(detector)
    alarm_timer_service = AlarmTimerService()
    if is_rpi and config["use_shairport-sync"]:
        shairport_handler = ShairportSyncHandler(detector, radio_player)
    app.config['detector'] = detector  # Attach detector to the Flask app config    
    loading_sound.stop_sound()
    detector.run()
    logger.info("Detector exited.")

def signal_handler(sig, frame):
    logger.info(f'Signal received: {sig}')
    logger.info('Exiting gracefully...')
    if detector is not None:
        detector.cleanup()
    if shairport_handler is not None:
        shairport_handler.cleanup()
    if radio_player is not None:
        radio_player.stop()
    if alarm_timer_service is not None:
        alarm_timer_service.cleanup()
    # No need to stop the LED server as we're not running it in this process
    if assistant.get('elevenlabs_voice_id', "") == "":
        tts_service = TextToSpeechService(config)
        tts_service.is_rpi = is_rpi
        tts_service.speak("Goodbye!")
        tts_service = None
    else:
        SoundEffectService(config).play("goodbye")
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def check_internet_connection(url='http://www.google.com/', timeout=5):
    try:
        response = requests.get(url, timeout=timeout)
        return True
    except requests.ConnectionError:
        return False
    
if __name__ == "__main__":
    #wait for up to 10 seconds for internet connection
    for i in range(10):
        if check_internet_connection():
            break
        time.sleep(1)
    if not check_internet_connection():
        logger.error("No internet connection. Please check your connection and try again.")
        tts_service = TextToSpeechService(config)
        tts_service.tts_engine = "pyttsx3"
        tts_service.is_rpi = is_rpi
        tts_service.speak("No internet connection")
        tts_service = None
        if is_rpi:
            led_service.handle_event("NoInternet")
    else:    
        if is_rpi:
            led_service.handle_event("Connected")
    
        if config["use_frontend"]:
            logger.info("Starting Flask frontend...")
            socketio.start_background_task(run_flask_app)
        runApp()
