import base64
from datetime import date
import gc
import json
import os
import platform
import queue
import re
import signal
import sys
import time
from typing import Iterable
import numpy as np
from chat_gpt_service import ChatGPTService
from input_listener import InputListener
import openwakeword
from openwakeword.model import Model
import pyaudio
from sound_effect_service import SoundEffectService
from tts_service import TextToSpeechService
import threading
from flask import Flask, jsonify, render_template, send_from_directory, request
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename
import requests

transcript_seperator = f"_"*40
script_dir = os.path.dirname(os.path.abspath(__file__))
detector = None
flask_thread = None
app = None
socketio = None
config = None
config_file = None
assistants = None
assistant_name = None
assistant_acronym = None
led_service = None
is_rpi = False
today = None
loading_sound = None
file_chunks = {}
is_exiting = False

# One-time download of all pre-trained models (or only select models)
openwakeword.utils.download_models()

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

led_service = None
# Check if the script is running on rpi
is_rpi= platform.system() == 'Linux' and is_running_on_raspberry_pi()
if is_rpi:
    try:
        from led_service import LEDService        
        led_service = LEDService()
        led_service.handle_event("Starting")
    except ImportError:
        print("Make sure you're running this on a Raspberry Pi.")
else:
    print("LED event: Starting")

config_file = os.path.join(script_dir, "config.json")
assistants_file = os.path.join(script_dir, "assistants.json")
print(f"Loading config from {config_file}...")
config = json.load(open(config_file))
print(f"Loading assistants from {assistants_file}...")
assistants = json.load(open(assistants_file))
assistant = assistants[config["assistant"]]
config["old_assistant"] = config["assistant"]
config["assistant_dict"] = assistant
assistant_name = assistant["name"]
assistant_acronym = assistant["acronym"]
vad_threshold = config["vad_threshold"]
print_audio_level = config["print_audio_level"]
today = str(date.today())
chatlog_filename = os.path.join(script_dir, "chatlogs", f"{config['assistant']}_chatlog-{today}.txt")
if not os.path.exists("chatlogs"):
    os.makedirs("chatlogs")

if config["use_frontend"]:
    app = Flask(__name__)
    socketio = SocketIO(app, async_mode='threading')


# save conversation to a log file 
def append2log(text, noNewLine=False):
    global today
    with open(chatlog_filename, "a", encoding='utf-8') as f:
        f.write(text + ("\n" if not noNewLine else ""))
        f.close
    
    if text and text != transcript_seperator:
        socketio.emit('update_chat', {'message': text.strip()})

class WakeWordDetector:
    def __init__(self):
        self.chat_gpt_service = ChatGPTService(config)
        self.chat_gpt_service.append2log = append2log
        oww_model_path = os.path.join(script_dir, "oww_models", config["oww_model"].replace("{assistant_name}", assistant_name))
        oww_inference_framework = config["oww_model"].split(".")[-1]
        self.language = config["language"]
        self.oww_chunk_size = config["oww_chunk_size"]
        self.oww_sample_rate = config["oww_sample_rate"]
        self.oww_channels = config["oww_channels"]
        self.is_request_processing = False
        self.is_awoken = False
        self.use_elevenlabs = config["use_elevenlabs"]
        self.audio_queue = queue.Queue()
        self.is_running = True
        self.producer_thread = None
        self.consumer_thread = None
        self.restart_app = False

        self.handle = Model(
            wakeword_models=[oww_model_path], 
            inference_framework=oww_inference_framework
        )

        self.pa = pyaudio.PyAudio()
        
        #stop loading sound so we can test ambient noise properly
        loading_sound.stop_sound()
        self.listener = InputListener(config)

        self.speech = TextToSpeechService(config)

        self.sound_effect = SoundEffectService(config)        

    def audio_producer(self):
        self._init_mic_stream()
        while self.is_running:
            try:
                if self.is_awoken:
                    #print("Audio producer paused")
                    while self.is_awoken:
                        time.sleep(1)
                #print("Audio producer resumed")
                oww_audio = np.frombuffer(self.mic_stream.read(self.oww_chunk_size, exception_on_overflow=False), dtype=np.int16)
                self.audio_queue.put(oww_audio)
            except IOError as e:
                if e.errno == pyaudio.paStreamIsStopped:
                    self._init_mic_stream()
                    continue
                else:
                    raise

    def audio_consumer(self):
        current_time = time.time()
        last_audio_level_emit_time = current_time
        last_audio_level_over_threshold = current_time
        while self.is_running:
            try:
                self.handle_led_event("Running")
                oww_audio = self.audio_queue.get()
                audio_level = np.abs(oww_audio).mean()
                if current_time - last_audio_level_emit_time >= 0.1:
                    socketio.emit('processing_audio', {'status': 'ready'})
                current_time = time.time()
                # if audio level is below the threshold, skip processing, 
                # but if the audio level was just above the threshold in the last 0.5 seconds, 
                # process the audio as its the tail end of the audio
                if audio_level < vad_threshold and current_time - last_audio_level_over_threshold > 0.75:
                    continue
                if audio_level > vad_threshold:
                    last_audio_level_over_threshold = current_time
                if print_audio_level:
                    print(f"Audio level threshold ({audio_level}) triggered. Processing audio...")
                # we don't want to send too many messages to the frontend. only send every audio level if its been 0.1 seconds
                if current_time - last_audio_level_emit_time >= 0.1:
                    socketio.emit('processing_audio', {'status': 'done', 'audio_level': audio_level})
                    last_audio_level_emit_time = time.time()
                prediction = self.handle.predict(oww_audio)
                prediction_models = list(prediction.keys())
                mdl = prediction_models[0]
                score = float(prediction[mdl])
                if score >= 0.5 and not self.is_request_processing:
                    socketio.emit('awake', {'status': 'ready'})
                    self.is_awoken = True
                    print(f"Awoken with score {round(score, 3)}!")
                    self.handle_led_event("Transcript")
                    self.sound_effect.play("awake")
                    socketio.emit('listening_for_prompt', {'status': 'ready'})
                    self.listener.listen()
                    self.handle_led_event("StreamingStarted")
                    socketio.emit('prompt_received', {'status': 'ready'})
                    self.listener.sound_effect = self.sound_effect.play_loop("loading")
                    self.listener.transcribe()
                    prediction = self.predictSilence()
                    if self.listener.transcript is None:
                        self.sound_effect.play("error")
                        self._init_mic_stream()
                        continue
                    self.process_transcript(self.listener.transcript)
            except Exception as e:
                self.something_went_wrong()
                print(f"Error: {e}")
                continue

    def process_audio(self):
        self.producer_thread = threading.Thread(target=self.audio_producer)
        self.consumer_thread = threading.Thread(target=self.audio_consumer)
        self.producer_thread.start()
        self.consumer_thread.start()
        while self.is_running:
            sys.stdout.flush()
            time.sleep(1)

    def handle_led_event(self, event):
        if led_service is not None:
            led_service.handle_event(event)
        else:
            if event == "Running":
                return
            print(f"LED event: {event}")

    def predictSilence(self):
        # Calculate the number of samples for the given duration of silence
        duration_seconds=2
        num_samples = int(self.oww_sample_rate * duration_seconds)
        silence_data = np.zeros(num_samples, dtype=np.int16)
        # Predict the silence data to initialize the model
        try:
            prediction = self.handle.predict(silence_data)
        except Exception as e:
            print(f"Error: {e}")
            pass
        return prediction

    def _init_mic_stream(self):
        self.handle_led_event("Connected")
        self.mic_stream = self.pa.open(
            rate=self.oww_sample_rate,
            channels=self.oww_channels,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.oww_chunk_size,
        )
        print("Listening for '" + assistant["wake_word"] + "'...")
        self.is_request_processing = False
        self.is_awoken = False
        socketio.emit('chatbot_ready', {'status': 'ready'})
    
    def something_went_wrong(self):
        if self.listener.sound_effect is not None:
            self.listener.sound_effect.stop_sound()
        if self.chat_gpt_service.sound_effect is not None:
            self.chat_gpt_service.sound_effect.stop_sound()
        self.sound_effect.play("error")
        if self.use_elevenlabs:
            self.sound_effect.play("something_went_wrong")
        else:
            self.speech.speak(f"Something went wrong!")
        self._init_mic_stream()

    def process_transcript(self, transcript, image=None, image_name=''):
        if self.is_request_processing:
            print("A request is already being processed. Please wait.")
            return 
        self.handle_led_event("Processing")
        self.is_request_processing = True
        try:
            start_time = time.time()
            print(f"You: {transcript}")
            append2log("")
            # if the user's question is none or too short, skip 
            if len(transcript) < 2 and not image:
                self.handle_led_event("VoiceStarted")
                short_response = "Hi, there, how can I help?"
                self.sound_effect.play("done")
                if self.use_elevenlabs:
                    self.sound_effect.play("hi_how_can_i_help")
                else:
                    self.speech.speak(f"Hi, how can I help?")
                append2log(f"You: {transcript} \n")
                append2log(f"{assistant_name}: {short_response} \n")
                self._init_mic_stream()
                return
            
            # new_convo_phrases = [
            #     "start a new conversation",
            #     "start a new chat",
            #     "forget the previous conversation",
            #     "forget what I said",
            #     "forget what I just said",
            #     "let's start over",
            # ]

            # if any(phrase in transcript for phrase in new_convo_phrases) and not image:
            #     append2log(f"You: {transcript} \n")
            #     self.sound_effect.play("done")
            #     # clear all but the first item in the chat history
            #     self.chat_gpt_service.history = self.chat_gpt_service.history[:1]
            #     self._init_mic_stream()
            #     return
            
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

            if any(phrase in transcript for phrase in time_phrases) and not image:
                append2log(f"You: {transcript} \n")
                # get the current time in am/pm format without leading zeros
                current_time = time.strftime('%I:%M %p').lstrip("0").replace("AM", "a.m.").replace("PM", "p.m.")
                response = f"{current_time}"
                self.sound_effect.play("done")
                #self.sound_effect.play("the_current_time_is")
                append2log(f"{assistant_name}: {response} \n")
                self.handle_led_event("VoiceStarted")
                self.speech.speak(response)
                self._init_mic_stream()
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

            if any(phrase in transcript for phrase in change_assistant_phrases) and not image:
                self.handle_led_event("VoiceStarted")
                print("Changing assistant...")
                append2log(f"You: {transcript} \n")
                # grab the assisant name from the transcript
                new_assistant = next((assistant for assistant in assistants if assistants.get(assistant, {}).get('name', '').lower() in transcript.lower()), None)
                new_assistant_name = assistants.get(new_assistant, {}).get('name', '')
                if new_assistant and new_assistant_name != assistant_name:
                    print(f"Switching to {new_assistant_name}...")
                    change_assistant({'assistant': new_assistant_name.lower()})
                elif new_assistant_name == assistant_name:
                    response = f"I'm already {assistant_name}."
                    print(response)
                    append2log(f"{assistant_name}: {response} \n")
                    self.speech.speak(response)
                else:
                    response = "Assistant not found."
                    print(response)
                    append2log(f"{assistant_name}: {response} \n")
                    self.speech.speak(response)
                self._init_mic_stream()
                return

            self.sound_effect.play("done")
            print("Sending to chat GPT...")
            append2log(f"You: {transcript}", noNewLine=True)
            self.chat_gpt_service.sound_effect = self.sound_effect.play_loop("loading")
            self.speech.sound_effect = self.chat_gpt_service.sound_effect

            text_iterator = self.chat_gpt_service.send_to_chat_gpt(transcript, image, image_name)
            if text_iterator is None:
                append2log(f"{assistant_name}: Something went wrong.")
                self.something_went_wrong()
                return

            end_time = time.time()
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

            print(f"Total Time: {end_time - start_time} seconds")
        finally:
            self._init_mic_stream()

    def run(self):
        try:
            self.handle_led_event("VoiceStarted")
            if self.use_elevenlabs:
                self.sound_effect.play("ready")
            else:
                self.speech.speak(f"{assistant_name} ready!")
            self.process_audio()
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

    def cleanup(self):
        self.is_running = False
        if self.producer_thread.is_alive():
            self.producer_thread.join()
        if self.consumer_thread.is_alive():
            self.consumer_thread.join()
        if self.mic_stream is not None:
            self.mic_stream.close()
        if self.pa is not None:
            self.pa.terminate()
        self.mic_stream = None
        self.pa = None
        self.speech = None
        self.sound_effect = None
        self.chat_gpt_service = None
        self.listener = None
        self.handle = None
        # Explicitly invoke garbage collection
        gc.collect()

@app.template_filter('find_url')
def find_url_filter(text):
    pattern = re.compile(r'(https?:\/\/[^\s]+\.(jpg|jpeg|png|gif))')
    #grab the first url found in the text
    url = pattern.search(text)[0] if pattern.search(text) else None
    return url if url else None

# Function to get chat logs for a specific date
def get_chat_log_for_date(date):
    filename = chatlog_filename.split("-")[0] + f"-{date}.txt"
    print(f"Getting chat log for {filename}...")
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

@app.route('/chatlog/<date>', methods=['GET'])
def chatlog(date):
    chatlog = get_chat_log_for_date(date)
    return jsonify(chatlog)

@app.route('/')
def index():
    chatlog = get_chat_log_for_date(today)
    return render_template('index.html', vad_threshold=vad_threshold, assistants=assistants, assistant_dict=assistant, images_disabled=config["use_groq"], chatlog=json.dumps(chatlog))

@socketio.on("file_chunk")
def handle_file_chunk(data):
    use_imgur = config["use_imgur"]
    socketio.emit('prompt_received', {'status': 'ready'})
    detector = app.config['detector']
    # Extracting the chunk data
    file_id = data.get("fileId")
    chunk_index = data.get("chunkIndex") or 0
    total_chunks = data.get("totalChunks") or 0
    if use_imgur:        
        chunk_data = data.get("chunkData") if data.get("chunkData") else None
    else:
        chunk_data = base64.b64decode(data.get("chunkData")) if data.get("chunkData") else None
    file_name = secure_filename(data.get("fileName")) if data.get("fileName") else None
    text_prompt = data.get("prompt") if data.get("prompt") else ""

    if file_id:
        print(f"Received chunk {chunk_index + 1} of {total_chunks} for file {file_id}")
        # Initialize the file's chunk list if not already
        if file_id not in file_chunks:
            file_chunks[file_id] = [None] * total_chunks

        # Store the chunk data
        file_chunks[file_id][chunk_index] = chunk_data

        # Check if all chunks have been received
        if all(chunk is not None for chunk in file_chunks[file_id]):
            # combine the chunks in memory
            print(f"Received all chunks for file {file_id}.")
            if not use_imgur:
                file_data = b"".join(file_chunks[file_id])
                upload_path = os.path.join(script_dir, config['upload_folder'])
                if not os.path.exists(upload_path):
                    os.makedirs(upload_path)

                # Sanitize the file_name or ensure it's safe before appending it to the path
                safe_file_name = os.path.join(upload_path, f"{time.time()}_{os.path.basename(file_name)}")
                # Reassemble the file
                with open(safe_file_name, "wb") as file:
                    for chunk in file_chunks[file_id]:
                        file.write(chunk)
                
                file_name = f"http://{request.host}/{safe_file_name}"
                file_data = base64.b64encode(file_data).decode("utf-8")
            else:
                file_data = "".join(file_chunks[file_id])

            # convert to base64
            response = detector.process_transcript(text_prompt, file_data, file_name)
            # delete the chunks from memory
            del file_chunks[file_id]
    else:
        response = detector.process_transcript(text_prompt)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(config['upload_folder'], filename)

@app.route('/history')
def history():
    chatlog = get_chat_log_for_date(today)
    return render_template('history.html', assistant_dict=assistant, chatlog=json.dumps(chatlog))

@socketio.on('change_vad_threshold')
def change_vad_threshold(data):
    global vad_threshold, config
    new_threshold = int(data.get('vad_threshold'))
    if new_threshold:
        vad_threshold = new_threshold
        with open(config_file, 'r+') as f:
            config = json.load(f)
            config['vad_threshold'] = new_threshold
            f.seek(0)
            json.dump(config, f, indent=4)
            f.truncate()
        print(f"VAD threshold changed to {new_threshold}.")
        socketio.emit('vad_threshold_changed', {'vad_threshold': new_threshold})
    return socketio.emit('vad_threshold_changed', {'vad_threshold': None})

@socketio.on('change_assistant')
def change_assistant(data):
    global config, assistant_name, assistant_acronym, assistant, chatlog_filename
    new_assistant = data.get('assistant')
    if new_assistant and new_assistant in assistants:
        with open(config_file, 'r+') as f:
            config = json.load(f)
            old_assistant = config['assistant']
            config['assistant'] = new_assistant
            f.seek(0)
            json.dump(config, f, indent=4)
            f.truncate()
        print(f"Assistant changed from {old_assistant} to {new_assistant}.")
        config["old_assistant"] = old_assistant
        config["assistant_dict"] = assistants[new_assistant]
        assistant = assistants[config["assistant"]]
        assistant_name = assistant["name"]
        assistant_acronym = assistant["acronym"]
        chatlog_filename = os.path.join(script_dir, "chatlogs", f"{config['assistant']}_chatlog-{today}.txt")
        socketio.emit('assistant_changed', {'assistant': new_assistant})
        restart_app()
        return
    return socketio.emit('assistant_changed', {'assistant': None})

def run_flask_app():
    socketio.run(app, debug=False, use_reloader=False, allow_unsafe_werkzeug=True, host="0.0.0.0")

def restart_app():
    global detector
    if detector is not None:
        detector.restart_app = True 
        detector.cleanup()

def runApp():
    global detector, loading_sound
    while True:
        loading_sound = SoundEffectService(config).play_loop("loading")
        detector = WakeWordDetector()
        app.config['detector'] = detector  # Attach detector to the Flask app config    
        detector.run()
        if not detector.restart_app:
            break
        else:
            detector = None

def signal_handler(sig, frame):
    global is_exiting
    if is_exiting:
        return
    is_exiting = True
    print('Exiting gracefully...')
    if detector is not None:
        detector.is_running = False
        detector.producer_thread.join()
        detector.consumer_thread.join()
    if is_rpi:
        led_service.turn_off()
    if config["use_elevenlabs"]:
        SoundEffectService(config).play("goodbye")
    else:
        TextToSpeechService(config).speak("Goodbye!")
    sys.exit(0)

def check_internet_connection(url='http://www.google.com/', timeout=5):
    try:
        response = requests.get(url, timeout=timeout)
        return True
    except requests.ConnectionError:
        return False
    
if __name__ == "__main__":
    if not check_internet_connection():
        print("No internet connection. Please check your connection and try again.")
        config["use_elevenlabs"] = False
        config["use_gtts"] = False
        TextToSpeechService(config).speak("No internet connection")
        if is_rpi:
            led_service.handle_event("NoInternet")
        signal_handler(signal.SIGINT, None)
    else:    
        if is_rpi:
            led_service.handle_event("Connected")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    if config["use_frontend"]:
        print("Starting Flask frontend...")
        socketio.start_background_task(run_flask_app)
    runApp()
