# JarvisChatBot - A Voice-Activated Chatbot using OpenAI and Raspberry Pi

[Flask Web UI](https://i.imgur.com/2ZNodii.jpeg)

## Introduction

This project is a voice-activated Raspberry Pi based system that listens for a wake word, "hey jarvis" or "jarvis". Upon hearing the wake word, the system starts recording audio input until it detects silence. It then sends this audio input to SpeechRecognition (google_recognizer) for transcription. Then it sends that transcription to one of several AI services (OpenAI, Groq, or Google Gemini) for further processing. The response from the AI service is then converted to speech using ElevenLabs or Google Text-to-Speech, and played back to the user. 

There is also a button service that can be used to start/stop the JarvisChatBot service with a quick press. And if held will shutdown the pi.

Flask is used to create a web interface that can be used to interact with the chatbot using websockets. The web interface can be accessed by navigating to the IP address of the Raspberry Pi on port 5000 (e.g., `http://localhost:5000`).
From there the chat log can be viewed and the chatbot can be sent text prompts along with images. FreeImage.host is the default for storing the images and the link is sent to the AI service for analysis.

The project now also includes a radio player feature that allows playing regular or kids' radio streams through voice commands or the web interface.

This was a quick hodge-podge project that still has lots of room for improvement. 

## Project Structure

The project is divided into several main python files:

1. **main.py**: The main script that integrates all other modules, listens for the wake word, manages the audio recording, and handles the interaction with various AI services.

2. **tts_service.py**: Handles the text-to-speech conversion using ElevenLabs or Google TTS.

3. **input_listener.py**: Handles the audio recording and silence detection.

4. **chat_gpt_service.py**: Manages the interaction with AI services (OpenAI, Groq, and Google Gemini).

5. **sound_effect_service.py**: Handles playing local sound effects.

6. **led_service.py**: Handles controlling the LED lights on the ReSpeaker 2-Mics Pi HAT.

7. **apa102.py**: A library for controlling the LED lights on the ReSpeaker 2-Mics Pi HAT.

8. **radio_player.py**: Handles playing radio streams from configured URLs.


There is also a configuration file, **config.json**, which stores important parameters and keys.

## Dependencies
This project uses:
- [Picovoice](https://picovoice.ai/): This is used to listen for the wake word.
- [SpeechRecognition](https://pypi.org/project/SpeechRecognition) (Google's legacy speech recognition engine)
- [OpenAI](https://openai.com/): One of the AI services used to respond to requests. You will need an API key from OpenAI to use this service.
- [Groq](https://groq.com/): Alternative AI service provider. You will need a Groq API key to use this service.
- [Google Gemini](https://ai.google.dev/): Another AI service provider. You will need a Google API key to use this service.
- [ElevenLabs](https://elevenlabs.io/): This is used to convert the response from the AI service into speech. You will need ElevenLabs credentials to use this service.
- [Google Text-to-Speech (gTTS)](https://gtts.readthedocs.io/): An alternative text-to-speech service.
- [mpv](https://mpv.io/): This is used to play the audio response.

## Configuration

All the keys and important parameters are stored in the `config.json` file. This includes:

- OpenAI API key (`openai_key`, `openai_model`, `system_prompt`): Used for interacting with OpenAI.
- Groq API key (`groq_key`, `groq_model`, `groq_vision_model`): Used for interacting with Groq.
- Google Gemini API key (`google_key`, `google_model`): Used for interacting with Google Gemini.
- ElevenLabs credentials (`elevenlabs_key`, `elevenlabs_voice_id`): Used for text-to-speech conversion with ElevenLabs.
- AI service selection (`ai_service`): Choose between "openai", "groq", or "google".
- Radio streams (`radio_stream_url`, `kids_radio_stream_url`): URLs for radio streaming.
- SpeechRecognition (`language`, `dynamic_energy_threshold`, `timeout`, `phrase_time_limit`): The language code for the speech recognition engine.
- Picovoice (`picovoice_key`): The Picovoice API key.
- Assistant configuration (`assistant_dict`): Contains assistant-specific settings including:
  - `name`: The assistant's name
  - `gender`: The assistant's gender ("male" or "female")
  - `accent`: The accent to use for speech
  - `speech_rate`: Words per minute for pyttsx3 speech (default: 175)

The `speech_rate` setting controls how fast the assistant speaks when using the pyttsx3 engine. Lower values make the speech slower, higher values make it faster. Some example values:
- 150: Slower, more deliberate speech
- 175: Moderate pace (default)
- 200: Faster pace
- 225: Very fast speech

## UI Features

The web interface includes:

1. **Chat interface**: View and interact with the chatbot through text and image uploads.
2. **Radio controls**: Play/stop regular and kids' radio streams.
3. **Settings page**: Configure AI services, models, and other options.
4. **Multiple assistant support**: Switch between different assistant personalities.
5. **Chat history**: View past conversations organized by date.
6. **Image Generation**: Generate images using the AI service (Google and OpenAI only).

## Running the Project

To run the project, execute the `main.py` script:

```
python main.py
```

# Obtaining Required Keys

This project requires keys from FreeImage.host, OpenAI, Groq, Google Gemini, and ElevenLabs. Here is how to obtain them:

1. **OpenAI Key**: Sign up at [openai.com](https://www.openai.com/) and follow the instructions [here](https://help.openai.com/en/articles/4936850-where-do-i-find-my-secret-api-key) to obtain your secret API key.

2. **Groq Key**: Sign up at [groq.com](https://groq.com/) to obtain your API key.

3. **Google Gemini Key**: Sign up at [ai.google.dev](https://ai.google.dev/) to obtain your API key.

4. **ElevenLabs Key**: Sign up at [ElevenLabs](https://elevenlabs.io/).

5. **FreeImage.host Key**: Sign up at [FreeImage.host](https://freeimage.host/).


After obtaining these keys, add them to your `config.json` file.

# Tested Environment and Installation Instructions

This project has been tested on a RaspberryPi 3b+ and a windows 11 desktop. The following sections provide instructions on how to set up the project on these systems.

For raspberry pi, I used the ReSpeaker 2-Mics Pi HAT as the sound card. More information about this sound card can be found [here](https://wiki.seeedstudio.com/ReSpeaker_2_Mics_Pi_HAT_Raspberry/).

For windows, I used a usb webcam mic and standard desktop speakers. 

## Raspberry Pi Setup

Below are the commands to set up the project on your Raspberry Pi:

1. **Install the ReSpeaker 2-Mics Pi HAT sound card**

```bash
sudo apt update -y
sudo apt upgrade -y
sudo apt install wireplumber portaudio19-dev libatlas-base-dev git python3-venv python3-pip ffmpeg flac espeak mpv build-essential libpython3-dev libdbus-1-dev libglib2.0-dev vlc -y
KERNEL_VERSION=$(uname -r | cut -d'.' -f1,2)
git clone --branch v$KERNEL_VERSION https://github.com/HinTak/seeed-voicecard
cd seeed-voicecard
sudo ./install.sh
sudo reboot now
```

2. **Clone the JarvisChatBot repository**

```bash
git clone https://github.com/MrSco/JarvisChatBot.git
cd JarvisChatBot
```

3. **Upgrade pip and install the required Python packages in a virtual environment**

```bash
bash ./install.sh
```

Now, your Raspberry Pi is set up to run the project. Remember to add your API keys to the `config.json` file before running the `main.py` script.

## Windows install requirements

For Windows

```bat
install.bat
```

# Edit the config.json file

Copy the `config.json.example` file to `config.json` and edit the file to include your OpenAI, Groq, Google Gemini, and ElevenLabs keys. Also copy the `assistants.json.example` file to `assistants.json`.


```bash
cp config.json.example config.json
cp assistants.json.example assistants.json
```

```bash
nano config.json
```

# Setting Up the Default Audio Output Device

In some instances, you may need to manually select the default audio output device. Here is how you can do it:

1. Open the Raspberry Pi configuration settings:

```bash
sudo raspi-config
```

2. Navigate through the menu options as follows:

```
1. System options  
S2. Audio
```

3. Select the desired audio output option. In our case, it was the `seeed-2mic-voicecard` option corresponding to the ReSpeaker sound card.

After you've selected the appropriate option, the system should use this device as the default for audio output.

4. Run alsamixer and set volume levels

```bash
alsamixer
mkdir -p ~/.config
alsactl -f ~/.config/asound.state store
sudo cp ~/.config/asound.state /var/lib/alsa/asound.state
```
5. (Optional) Adjust alsa-restore.service and add the -U parameter to the exestart restore command:

```bash
sudo nano /usr/lib/systemd/system/alsa-restore.service
```

```bash
ExecStart=-/usr/sbin/alsactl -E HOME=/run/alsa -E XDG_RUNTIME_DIR=/run/alsa/runtime -U restore
```

## Using as an AirPlay speaker with ShairPort-Sync

If you want to use the ReSpeaker 2-Mics Pi HAT as an AirPlay speaker, you can use ShairPort-Sync. Here's how to set it up:

1. **Install ShairPort-Sync**

```bash
sudo apt install shairport-sync -y
```

2. **Edit the ShairPort-Sync configuration file**

```bash
sudo nano /etc/shairport-sync.conf
```

3. **Change the `port` field to something other then 5000 (I use 5555)**

4. **Start the ShairPort-Sync service**

```bash
sudo systemctl start shairport-sync
```

## Running as a Service

1. **Create a jarvischatbot Service File**
Use the included jarvischatbot.service file to create a service that will run the JarvisChatBot script on startup. Modify the file to include the correct path to the JarvisChatBot directory.

```bash
sudo cp jarvischatbot.service /etc/systemd/system/jarvischatbot.service
sudo nano /etc/systemd/system/jarvischatbot.service
```

2. **Enable the Service**

```bash
sudo systemctl enable jarvischatbot.service
```

3. **Start the Service**

```bash
sudo systemctl start jarvischatbot.service
```

Now, the JarvisChatBot script will run as a service on startup.

## Running Button Service

1. **Create a button Service File**
Use the included 2mic_button.service file to create a service that will run the button script on startup. The button will start/stop the JarvisChatBot service with a quick press. And if held will shutdown the pi.
Modify the file to include the correct path to the JarvisChatBot directory.

```bash
sudo cp 2mic_button.service /etc/systemd/system/2mic_button.service
sudo nano /etc/systemd/system/2mic_button.service
```

2. **Enable the Service**

```bash
sudo systemctl enable 2mic_button.service
```

3. **Start the Service**

```bash
sudo systemctl start 2mic_button.service
```

Now, the button script will run as a service on startup.

## Running the startup_shutdown_sounds Service

1. **Create a startup_shutdown_sounds Service File**
Use the included startup_shutdown_sounds.service file to create a service that will play a startup sound and a shutdown sound on startup and shutdown. Modify the file to include the correct path to the JarvisChatBot directory.

```bash
sudo cp startup_shutdown_sounds.service /etc/systemd/system/startup_shutdown_sounds.service
sudo nano /etc/systemd/system/startup_shutdown_sounds.service
```

2. **Enable the Service**

```bash
sudo systemctl enable startup_shutdown_sounds.service
```

3. **Start the Service**

```bash
sudo systemctl start startup_shutdown_sounds.service
```

Now, the startup_shutdown_sounds script will run as a service on startup.

## LED Lights

The ReSpeaker 2-Mics Pi HAT has LED lights that can be controlled. The `led_service.py` script can be used to control these lights. The script uses the `apa102.py` library to control the LEDs.

LED Color Legend:
- Purple: Starting up
- Green: Started (or reinitalizing wake word)
- Red: Ready and Listening for wake word
- Blue: No Internet Connection
- White: Listening for user input
- Cyan: Transcribing user input
- Pink: Processing user input
- Yellow: Responding to user input
- Orange: Shutting down
- Flashing Orange: Airplay Connected to ShairPort-Sync
- Off: Not running


## AirPlay Speaker support via ShairPort-Sync

The Raspberry Pi can be used as an AirPlay speaker using ShairPort-Sync. Whether the chatbot is running or not, you can stream audio to the Raspberry Pi using AirPlay. 
If running, the microphone will be muted and the LED lights will flash orange when connected to ShairPort-Sync. After disconnecting, the microphone will be unmuted and the LED lights will return to normal.

## Alarms and Timers

The JarvisChatBot can be used to set alarms and timers. systemd (and scheduled tasks on windows) are used to store the alarms and timers. 
You can use the phrases `set an alarm for 6:30 am` or `set a timer for 10 minutes` to set an alarm or timer.

## Radio Player

The JarvisChatBot now includes a radio player feature that allows streaming radio from configured URLs. You can control it through:

1. **Voice commands**: Say phrases like "play radio", "play kids radio", or "stop radio"
2. **Web interface**: Use the buttons on the web interface to start/stop radio streams

The radio URLs can be configured in the settings page or directly in the config.json file:
- `radio_stream_url`: URL for the main radio stream
- `kids_radio_stream_url`: URL for the kids' radio stream

## Multi-AI Provider Support

The project now supports multiple AI service providers:

1. **OpenAI**: Traditional GPT models including GPT-4o
2. **Groq**: Fast LLama and Mixtral model inferencing
3. **Google Gemini**: Google's Gemini models with image understanding capabilities

You can switch between providers in the settings page. Each provider has its own set of models to choose from, and the UI will dynamically update to show only the relevant options for the selected provider.

Note that when using Google Gemini, some features like FreeImage.host integration are automatically disabled as Gemini handles images differently.

## Limitations

Please note that this project was forked from a project that was developed for hackathon and demo purposes. Therefore, there is no guarantee for its performance or functionality.

## Acknowledgements

This documentation was written by ChatGPT with some supervision by the author

## Disclaimer

This project is a fan-made, non-commercial project and is not affiliated with, endorsed by, or associated with Marvel, Disney, or any of their subsidiaries. All characters, images, and other related materials are the property of their respective owners. No copyright infringement is intended. This project is for entertainment purposes only, and no monetary gain is being made from its distribution. If any copyright holder feels that their intellectual property has been used inappropriately, please contact me and the content will be removed immediately.




