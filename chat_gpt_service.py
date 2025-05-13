import base64
import json
import threading
import time
import types
import openai
from groq import Groq
from google import genai
from google.genai import types
import urllib
import geocoder
from datetime import date, datetime
import requests
from tzlocal import get_localzone
import os
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

class ChatGPTService:
    def __init__(self, config):
        self.append2log = None
        self.chatlog = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chatlogs", f"{config['assistant']}_chatlog-{str(date.today())}.txt")
        self.assistant_name = config["assistant_dict"]["name"]
        self.assistant_acronym = config["assistant_dict"]["acronym"]
        self.assistant_descr = config["assistant_dict"]["descr"]
        self.system_prompt = config["system_prompt"]
        self.weather_info = self.get_weather_url()
        self.system_prompt = config["system_prompt"] \
            .replace("{assistant_name}", self.assistant_name) \
            .replace("{assistant_acronym}", self.assistant_acronym) \
            .replace("{assistant_descr}", self.assistant_descr)
        self.system_prompt_msg = {"role": "system", "content": self.system_prompt}
        
        # Initialize history with system prompt
        self.history = [self.system_prompt_msg]
        
        # If there's an existing chatlog file, load it into history
        if os.path.exists(self.chatlog) and os.path.isfile(self.chatlog):
            try:
                with open(self.chatlog, 'r', encoding='utf-8') as f:
                    chatlog_content = f.read()
                
                # Parse the chatlog content to extract messages
                messages = []
                lines = chatlog_content.split('\n')
                current_role = None
                current_content = ""
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check for user or assistant message indicators
                    if line.startswith("You:"):
                        # Save previous message if exists
                        if current_role and current_content.strip():
                            messages.append({"role": current_role, "content": current_content.strip()})
                        
                        # Start a new user message
                        current_role = "user"
                        current_content = line[len("You:"):].strip()
                    elif line.startswith(f"{self.assistant_name}:"):
                        # Save previous message if exists
                        if current_role and current_content.strip():
                            messages.append({"role": current_role, "content": current_content.strip()})
                        
                        # Start a new assistant message
                        current_role = "assistant"
                        current_content = line[len(f"{self.assistant_name}:"):].strip()
                    else:
                        # Continue current message
                        current_content += " " + line
                
                # Add the last message
                if current_role and current_content.strip():
                    messages.append({"role": current_role, "content": current_content.strip()})
                
                # Load messages into history (system prompt + last 4 messages)
                if messages:
                    logger.info(f"Initializing history with {len(messages)} messages from chatlog file")
                    
                    # Limit to last 4 messages (2 turns) to keep context window manageable
                    if len(messages) > 4:
                        messages = messages[-4:]
                    
                    # Set history with system prompt + parsed messages
                    self.history = [self.system_prompt_msg] + messages
                    
                    logger.info(f"Loaded {len(self.history) - 1} messages into history")
            except Exception as e:
                logger.error(f"Error loading chatlog: {e}")
                # Fall back to just system prompt
                self.history = [self.system_prompt_msg]
        
        self.ai_service = config.get("ai_service", "openai")
        
        # Initialize API keys for each service
        os.environ["GOOGLE_API_KEY"] = config.get("google_key", "")
        os.environ["GROQ_API_KEY"] = config.get("groq_key", "")
        os.environ["OPENAI_API_KEY"] = config.get("openai_key", "")
    
        # Fetch available models for all providers
        self.available_models = {}
        self.fetch_all_available_models()
        
        # Store models in config for frontend access
        config['available_models'] = self.available_models
        
        if self.ai_service == "google":
            self.model = config["google_model"]
            # Initialize Google Gemini client
            self.llm = genai.Client()
            current_time = datetime.now(get_localzone()).strftime('%I:%M %p %Z').lstrip("0")
            # Create the chat instance with system prompt
            self.chat = self.llm.chats.create(
                model=self.model, 
                config=types.GenerateContentConfig(system_instruction=self.system_prompt.replace("{today}", str(date.today())).replace("{theCurrentTime}", current_time))
            )
        elif self.ai_service == "groq":
            self.model = config["groq_model"]
            self.llm = Groq()
        else:
            self.model = config["openai_model"]
            self.llm = openai
        self.sound_effect = None
        self.image_storage = config["image_storage"]
        self.freeimage_key = config["freeimage_key"]
        self.upload_folder = config["upload_folder"]
        self.host = None
        self.port = None
        self.speech = None
        self.handle_led_event = None
        # Initialize DuneWeaver support
        self.duneweaver = None
        self.duneweaver_url = config.get("duneweaver_url", "")
        if self.duneweaver_url:
            # Import and initialize DuneWeaver only when needed
            from duneweaver import DuneWeaver
            self.duneweaver = DuneWeaver(config)

    def getMimeType(self, fileExtension):
        mime_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'webp': 'image/webp',
            'tiff': 'image/tiff'
        }
        return mime_types.get(fileExtension, 'image/jpeg')

    def get_current_location(self):
        try:
            g = geocoder.ip('me')
            logger.info(f"Current location: {g.city}, {g.state}, {g.country}")
            return g.city
        except Exception as e:
            logger.error(f"Failed to get current location: {e}")
            return None

    def get_weather_location_and_url(self, location=None):
        if location is None:
            location = self.get_current_location() or 'Miami'  # Default to Miami if location can't be determined
        location_unparsed = location  # Save the unparsed location for later use
        location = urllib.parse.quote(location)  # URL-encode the location
        return {"location_name": location_unparsed, "weather_url": f'http://wttr.in/{location}?format=j1'}
    
    def get_weather_url(self, location=None):
        weather_location_and_url = self.get_weather_location_and_url(location)
        location_unparsed = weather_location_and_url["location_name"]
        url = weather_location_and_url["weather_url"]
        return f"Current and forecast weather json data for ({location_unparsed}) can be found here: {url}. "
        
    def get_weather_info(self, location=None):
        weather_location_and_url = self.get_weather_location_and_url(location)
        location_unparsed = weather_location_and_url["location_name"]
        url = weather_location_and_url["weather_url"]
        try:
            logger.info(f"Getting weather information from: {url}")
            with urllib.request.urlopen(url) as response:
                if response.status == 200:
                    return f"Current and forecast weather json data for ({location_unparsed}) (source: {url}): {response.read()}"
                else:
                    logger.warning("Weather information is not available at the moment.")
                    return ""
        except urllib.error.URLError as e:
            logger.error(f"Failed to get weather information: {e.reason}")
            return ""

    def upload_image_to_freeimage(self, image_data, filename=''):
        """
        Upload an image to FreeImage.host service
        Args:
            image_data: Either a URL string or binary image data
            filename: Original filename
        Returns:
            str: URL of the uploaded image or empty string if upload fails
        """
        try:
            upload_url = "https://freeimage.host/api/1/upload"
            
            # Check if input is bytes (binary data) or string (URL)
            if isinstance(image_data, str):
                # For URL uploads
                params = {
                    'key': self.freeimage_key,
                    'source': image_data,
                    'action': 'upload'
                }
                response = requests.post(upload_url, data=params)
            else:
                # Get file extension from filename
                ext = os.path.splitext(filename)[1].lower()
                mime_type = self.getMimeType(ext)
                
                # For direct file uploads using binary data
                files = {
                    'source': (filename, image_data, mime_type)
                }
                params = {
                    'key': self.freeimage_key,
                    'action': 'upload'
                }
                response = requests.post(upload_url, data=params, files=files)
            
            if response.status_code != 200:
                raise Exception(f"Failed to upload: {response.text}")
            
            file_url = response.json()["image"]["url"]
            logger.info(f"Image uploaded successfully to FreeImage.host! {file_url}")
            return file_url

        except Exception as e:
            logger.error(f"Failed to upload image to FreeImage.host: {e}")
            return ""

    def is_image_generation_request(self, request):
        """Check if the request is asking for image generation"""
        image_keywords = [
            "generate an image",
            "create an image",
            "make an image",
            "draw an image",
            "draw a picture",
            "create a picture",
            "generate a picture",
            "make a picture",
            "show me a picture",
            "show me an image",
            "create a visual",
            "generate a visual",
            "make a visual",
            "make a photo",
            "make a photograph",
            "make a drawing",
            "make a painting",
            "make a sketch",
            "draw a painting",
            "draw a sketch"
        ]
        return any(keyword in request.lower() for keyword in image_keywords)

    def generate_image(self, prompt):
        """Generate an image using the appropriate service"""
        try:
            if self.ai_service == "google":
                # Use Gemini's image generation
                response = self.llm.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=['Text', 'Image']
                    )
                )
                
                # Extract the image data from the response
                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        return part.inline_data.data
            elif self.ai_service == "openai":
                # Use OpenAI's DALL-E
                response = self.llm.images.generate(
                    model=self.model,
                    prompt=prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                # Get the image URL from the response
                image_url = response.data[0].url
                # Download the image data
                response = requests.get(image_url)
                return response.content
            elif self.ai_service == "groq":
                return None
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            return None

    def save_file(self, file_data, filename, file_mode = 'wb', use_timestamp = True):
        try:
            upload_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.upload_folder)
            if not os.path.exists(upload_path):
                os.makedirs(upload_path)
            if use_timestamp:
                filename = f"{time.time()}_{os.path.basename(filename)}"
            else:
                filename = os.path.basename(filename)
            safe_file_name = os.path.join(upload_path, filename)
            with open(safe_file_name, file_mode) as f:
                f.write(file_data)
            #return the full path to the file
            return safe_file_name
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            return ""

    def save_generated_image(self, image_data, filename):
        try:
            # Store the image based on configuration
            if self.image_storage == "freeimage":
                image_url = self.upload_image_to_freeimage(image_data, filename)
            else:
                safe_file_name = os.path.basename(self.save_file(image_data, filename))
                image_url = f"http://{self.host}:{self.port}/{self.upload_folder}/{safe_file_name}"
            return image_url
        except Exception as e:
            logger.error(f"Error saving generated image: {e}")
            return ""
        
    def send_to_chat_gpt(self, request, image=None, image_link=''):
        modelToUse = self.model
        image_url = ''
        image_format = 'image/jpeg'
        emptyRequest = request == ''
        defaultImageRequest = 'Describe this image.'
        # replace the timestamp in the history with the current time
        current_time = datetime.now(get_localzone()).strftime('%I:%M %p %Z').lstrip("0")
        if self.history and self.history[0]["role"] == "system":
            self.history[0]["content"] = self.system_prompt.replace("{today}", str(date.today())) \
                .replace("{theCurrentTime}", current_time) \
                .replace("{weather_info}", self.weather_info)
        
        # Check if this is a DuneWeaver request when URL is configured
        if self.duneweaver and self.duneweaver.dw_prompt and self.duneweaver.is_duneweaver_request(request):
            # Extract the prompt from the request
            image_desc = self.duneweaver.extract_draw_prompt(request)
            if "stop" in image_desc.lower():
                rtnMsg = "Stopping DuneWeaver execution."
                self.duneweaver.stop_execution()
                self.append2log(f"\n\n{self.assistant_name}: {rtnMsg}")
                return [rtnMsg]
            canned_response = "I'm creating a sand pattern for you... "
            self.append2log(f"\n\n{self.assistant_name}: {canned_response}", True)
            

            dw_prompt = self.duneweaver.dw_prompt.replace("{{}}", image_desc)
            
            pattern_filename = image_desc.replace(' ', '_') + '.thr'
            
            # check if we already have that pattern on duneweaver
            theta_rho_file = os.path.join("custom_patterns", os.path.basename(pattern_filename)).replace('\\', '/')
            theta_rho_files = self.duneweaver.list_theta_rho_files()
            # check our list of theta_rho files. If its none or we already have a match to the theta_rho_file, skip the image generation
            if theta_rho_files is None:
                rtnMsg = "I couldn't reach the sand table. Please try again later."
                self.append2log(f"{rtnMsg}")
                return [rtnMsg]
            elif any(theta_rho_file in file for file in theta_rho_files):
                logger.info(f"Skipping image generation for: {theta_rho_file} because it already exists on duneweaver")
                # Run the pattern on DuneWeaver
                runResponse = self.duneweaver.run_theta_rho(theta_rho_file)
                if not runResponse.get("success", False):
                    detailMsg = runResponse['detail'].split(':')[1].strip()
                    rtnMsg = f"I couldn't run the pattern on the sand table. {detailMsg}"
                    self.append2log(f"{rtnMsg}")
                    return [rtnMsg]
            else:
                logger.info(f"No existing theta_rho files named {theta_rho_file} found")
                # Generate the image
                image_data = self.generate_image(dw_prompt)
                if not image_data:
                    rtnMsg = "I couldn't generate the image for your sand pattern."
                    self.append2log(f"{rtnMsg}")
                    return [rtnMsg]
                
                # Store the generated image to display later
                image_url = self.save_generated_image(image_data, pattern_filename.replace('.thr', '.png'))
            
                # while the pattern is generating,
                # stop the loading sound and change the led to flash "VoiceStarted" on a separate thread 
                # speak a message to the user that the pattern is being generated
                # then we can set the led back to solid "VoiceStarted" and start the loading sound again after the pattern is generated
                # we can use a thread to handle the led flashing and sound playing so it doesn't block the main thread
                self.sound_effect.stop_sound()
                self.speech.speak("I'm creating a sand pattern for you... ")
                blink_leds = True
                def blink_leds():
                    while blink_leds:
                        self.handle_led_event("VoiceStarted")
                        time.sleep(0.5)
                        self.handle_led_event("Off")
                        time.sleep(0.5)

                blink_leds_thread = threading.Thread(target=blink_leds)
                blink_leds_thread.start()
                # Convert the image to a sand pattern
                sand_pattern = self.duneweaver.convert_image_to_sand_pattern(image_data)
                if not sand_pattern:
                    blink_leds = False
                    if blink_leds_thread is not None and blink_leds_thread.is_alive():
                        blink_leds_thread.join()
                    rtnMsg = "I couldn't convert the image to a sand pattern."
                    self.append2log(f"{rtnMsg}")
                    return [rtnMsg]
                blink_leds = False
                if blink_leds_thread is not None and blink_leds_thread.is_alive():
                    blink_leds_thread.join()
                logger.info("Sand pattern generated...")
                self.sound_effect.play_loop("loading")
                self.handle_led_event("VoiceStarted")
                
                # Save the sand pattern to a file
                sand_pattern_filename = self.save_file(sand_pattern, pattern_filename, 'w', False)

                if not sand_pattern_filename:
                    rtnMsg = "I couldn't save the sand pattern to a file."
                    self.append2log(f"{rtnMsg}")
                    return [rtnMsg]
            
                # Send the pattern to DuneWeaver
                uploadResponse = self.duneweaver.upload_theta_rho(sand_pattern_filename)
                if not uploadResponse.get("success", False):
                    os.unlink(sand_pattern_filename)
                    detailMsg = uploadResponse['detail'].split(':')[1].strip()
                    rtnMsg = f"I couldn't send the pattern to the sand table. {detailMsg}"
                    self.append2log(f"{rtnMsg}")
                    return [rtnMsg]
                os.unlink(sand_pattern_filename)
                
                # Run the pattern on DuneWeaver
                runResponse = self.duneweaver.run_theta_rho(theta_rho_file)
                if not runResponse.get("success", False):
                    detailMsg = runResponse['detail'].split(':')[1].strip()
                    rtnMsg = f"I couldn't run the pattern on the sand table. {detailMsg}"
                    self.append2log(f"{rtnMsg}")
                    return [rtnMsg]
            
            success_message = "Pattern sent to the sand table! Here's the image I generated:"
            self.append2log(f"{success_message}\n\n{image_url}\n\n", True)
            return [success_message]
        
        # Check if this is an image generation request
        if self.is_image_generation_request(request):
            canned_response = "Here is the image you wanted - "
            self.append2log(f"\n\n{self.assistant_name}: {canned_response}", True)
            
            # Generate the image
            image_data = self.generate_image(request)
            if image_data:
                generated_image_filename = "generated_image.png"
                image_url = self.save_generated_image(image_data, generated_image_filename)
                
                # Add the image URL to the chat log
                self.append2log(f"{image_url}\n\n", True)
                return [canned_response]
            else:
                return ["I couldn't generate the image you requested."]

        if image is not None:
            if self.image_storage == "freeimage" and not self.ai_service == "google":
                image_url = self.upload_image_to_freeimage(image, image_link)
            else:
                # determine image mime type file extension
                image_format = self.getMimeType(image_link.split('.')[-1] if image_link else 'jpg')
                image_url = f"data:{image_format};base64,{base64.b64encode(image).decode('utf-8')}"

            if image_link != '':
                if emptyRequest:
                    request = defaultImageRequest
                content = [{"type": "text", "text": "respond as concisely as possible to the following request: " + request}, {"type": "image_url", "image_url": {"url": image_url}}]
            else:
                return None

            if self.ai_service == "groq":
                # Clear history for image requests
                self.history = []
        else:
            content = request
            # For non-image requests, ensure system prompt is first in history
            if not self.history or self.history[0]["role"] != "system":
                self.history.insert(0, self.system_prompt_msg)
            # Clean up history to ensure all content is strings
            self.history = [
                msg if isinstance(msg["content"], str) else 
                {"role": msg["role"], "content": msg["content"][0]["text"] if isinstance(msg["content"], list) else ""} 
                for msg in self.history
            ]

        self.history.append({"role": "user", "content": content})
        if len(self.history) > 5 and not image:
            self.history = [self.history[0]] + self.history[-4:]
        result = None
        try:
            #logger.debug(self.history)
            logger.info(f"Sending to {self.ai_service} {modelToUse}...")
            if self.ai_service == "google":
                if self.history and self.history[0]["role"] == "system":
                    system_prompt = self.history[0]["content"]
                else:
                    system_prompt = self.system_prompt
                # Use the Gemini API according to documentation
                if image is not None:
                    # For image inputs
                    if isinstance(content, list):
                        # Extract text and image parts
                        prompt_text = next((item["text"] for item in content if item["type"] == "text"), "")
                        #image_part = next((item["image_url"]["url"] for item in content if item["type"] == "image_url"), "")
                        image_part = types.Part.from_bytes(
                            data=image,
                            mime_type=image_format
                        )
                        # Create multipart content for Gemini
                        gemini_contents = [prompt_text, image_part]
                        response = self.llm.models.generate_content_stream(
                            model=modelToUse,
                            config=types.GenerateContentConfig(
                                system_instruction=system_prompt),
                            contents=gemini_contents
                        )
                    else:
                        response = self.llm.models.generate_content_stream(
                            model=modelToUse,
                            config=types.GenerateContentConfig(
                                system_instruction=system_prompt),
                            contents=[content]
                        )
                else:                    
                    # Send the current message and stream the response using the existing chat instance
                    # Add previous messages to chat history, if any
                    if len(self.history) > 1:
                        # Instead of recreating the chat, track which messages we've already sent
                        # Skip system message (0) and the most recent user message (last)
                        # Get only the new messages that need to be added to maintain context
                        unprocessed_history = []
                        for i, msg in enumerate(self.history[1:-1]):  # Skip system message and latest user message
                            if msg["role"] == "user":
                                unprocessed_history.append(msg)
                        
                        # Get last 3 user messages to match the 5 message context window (system + 3 previous + current)
                        for msg in unprocessed_history[-3:]:
                            logger.info(f"Adding previous message to Google chat: {msg['content'][:30]}...")
                            self.chat.send_message(msg["content"])
                    
                    response = self.chat.send_message_stream(self.history[-1]["content"])
            else:
                response = self.llm.chat.completions.create(
                    model=modelToUse, 
                    messages=self.history,
                    temperature=0.7,
                    stream=True
                )
            
            self.append2log(f"{defaultImageRequest if emptyRequest else ''} {image_url if not image_link else image_link} \n\n", True)
        
        except Exception as e:
            result = "Unknown Error "
            logger.error(result + str(e))
            return result
        
        def text_iterator():
            response_full_text = ""
            sentence = ""
            sentence_endings = {'.', '!', '?'}  # Remove ellipses from endings set
            self.append2log(f"{self.assistant_name}: ", True)
            
            def process_sentence(current_sentence):
                # First check for regular sentence endings
                for ending in sentence_endings:
                    pos = current_sentence.find(ending)
                    if pos >= 0:
                        # Make sure this isn't part of an ellipsis
                        if not (ending == '.' and 
                              (pos + 2 < len(current_sentence) and current_sentence[pos:pos+3] == '...' or
                               pos > 0 and current_sentence[pos-2:pos+1] == '...')):
                            
                            # Count quotes before the sentence ending
                            quotes_before = current_sentence[:pos+1].count('"')
                            
                            # If we have an odd number of quotes, look for the closing quote
                            if quotes_before % 2 == 1:
                                next_quote = current_sentence[pos+1:].find('"')
                                if next_quote >= 0:
                                    pos = pos + 1 + next_quote
                            
                            complete = current_sentence[:pos+1].strip()
                            remainder = current_sentence[pos+1:].lstrip()
                            
                            if len(complete) > 1:  # More than just punctuation
                                self.append2log(complete, True)
                                logger.info(f"Complete sentence: {complete}")
                                return complete, remainder
                
                # Handle ellipsis as a sentence ending only if:
                # 1. It's followed by a space or end of string
                # 2. It's not just standalone ellipsis
                ellipsis_pos = current_sentence.find('...')
                if ellipsis_pos >= 0:
                    # Check if there's content before the ellipsis
                    has_content_before = ellipsis_pos > 0 and not current_sentence[:ellipsis_pos].isspace()
                    # Check if it's at the end or followed by space
                    is_at_end = ellipsis_pos + 3 >= len(current_sentence) or current_sentence[ellipsis_pos + 3].isspace()
                    
                    if has_content_before and is_at_end:
                        complete = current_sentence[:ellipsis_pos + 3].strip()
                        remainder = current_sentence[ellipsis_pos + 3:].lstrip()
                        if len(complete) > 3:  # More than just the ellipsis
                            self.append2log(complete, True)
                            logger.info(f"Complete sentence: {complete}")
                            return complete, remainder
                
                return None, current_sentence.lstrip()  # Also strip any leading whitespace from incomplete sentences
            
            if self.ai_service == "google":
                # Process Google Gemini response stream
                for chunk in response:
                    if hasattr(chunk, 'text') and chunk.text:
                        text_content = chunk.text.strip('"')
                        sentence += text_content
                        response_full_text += text_content
                        
                        complete, sentence = process_sentence(sentence)
                        if complete:
                            yield complete
            else:
                # Process OpenAI/Groq response stream
                for chunk in response:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        text_content = delta.content.strip('"')
                        sentence += text_content
                        response_full_text += text_content
                        
                        complete, sentence = process_sentence(sentence)
                        if complete:
                            yield complete
            
            # Yield any remaining text after the loop ends
            if sentence:
                self.append2log(sentence)
                yield sentence
            else:
                self.append2log("")
            self.history.append({"role": "assistant", "content": response_full_text})
        
        return text_iterator()

    # Add methods to fetch available models for each provider
    def fetch_openai_models(self):
        """Fetch available OpenAI models"""
        try:
            if not os.environ.get("OPENAI_API_KEY"):
                return []
                
            models = openai.models.list()
            chat_models = [model.id for model in models]
            # Sort the models alphabetically
            chat_models.sort()
            return chat_models
        except Exception as e:
            logger.error(f"Error fetching OpenAI models: {e}")
            return []

    def fetch_groq_models(self):
        """Fetch available Groq models"""
        try:
            if not os.environ.get("GROQ_API_KEY"):
                return []
                
            client = Groq()
            models = []
            # The response is a ModelListResponse object with a 'data' attribute
            model_list = client.models.list()
            
            # Access the data attribute which contains the list of models
            if hasattr(model_list, 'data'):
                for model in model_list.data:
                    # Each model is an object with an 'id' attribute
                    if hasattr(model, 'id'):
                        models.append(model.id)
            
            # Sort the models alphabetically
            models.sort()
            
            return models
        except Exception as e:
            logger.error(f"Error fetching Groq models: {e}")
            return []

    def fetch_google_models(self):
        """Fetch available Google Gemini models"""
        try:
            if not os.environ.get("GOOGLE_API_KEY"):
                return []
                
            client = genai.Client()
            text_models = []
            for m in client.models.list():
                for action in m.supported_actions:
                    if action == "generateContent":
                        text_models.append(m.name.replace("models/", ""))
                        break
            # Sort the models alphabetically
            text_models.sort()
            return text_models
        except Exception as e:
            logger.error(f"Error fetching Google models: {e}")
            return []

    def fetch_all_available_models(self):
        """Fetch available models for all providers"""
        self.available_models = {
            'openai': self.fetch_openai_models(),
            'groq': self.fetch_groq_models(),
            'google': self.fetch_google_models()
        }
        logger.info(f"Fetched available models: {len(self.available_models['openai'])} OpenAI, {len(self.available_models['groq'])} Groq, {len(self.available_models['google'])} Google")
        return self.available_models
