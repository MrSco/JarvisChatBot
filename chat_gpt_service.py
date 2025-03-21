import base64
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

class ChatGPTService:
    def __init__(self, config):
        self.append2log = None
        self.ai_service = config.get("ai_service", "openai")
        
        if self.ai_service == "google":
            os.environ["GOOGLE_API_KEY"] = config["google_key"]
            self.model = config["google_model"]
            # Initialize Google Gemini client
            self.llm = genai.Client()
        elif self.ai_service == "groq":
            os.environ["GROQ_API_KEY"] = config["groq_key"]
            self.model = config["groq_model"]
            self.groq_vision_model = config["groq_vision_model"]
            self.llm = Groq(api_key=config["groq_key"])
        else:
            os.environ["OPENAI_API_KEY"] = config["openai_key"]
            self.model = config["openai_model"]
            self.llm = openai
        self.assistant_name = config["assistant_dict"]["name"]
        self.assistant_acronym = config["assistant_dict"]["acronym"]
        self.assistant_descr = config["assistant_dict"]["descr"]
        self.system_prompt = config["system_prompt"]
        self.weather_info = "" #self.get_weather_url()
        self.system_prompt = config["system_prompt"] \
            .replace("{assistant_name}", self.assistant_name) \
            .replace("{assistant_acronym}", self.assistant_acronym) \
            .replace("{assistant_descr}", self.assistant_descr) \
            .replace("{weather_info}", self.weather_info)
        self.system_prompt_msg = {"role": "system", "content": self.system_prompt}
        self.history = [self.system_prompt_msg]
        self.sound_effect = None
        self.image_storage = config["image_storage"]
        self.freeimage_key = config["freeimage_key"]
        self.upload_folder = config["upload_folder"]
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5000)

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
            print(f"Current location: {g.city}, {g.state}, {g.country}")
            return g.city
        except Exception as e:
            print(f"Failed to get current location: {e}")
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
            print(f"Getting weather information from: {url}")
            with urllib.request.urlopen(url) as response:
                if response.status == 200:
                    return f"Current and forecast weather json data for ({location_unparsed}) (source: {url}): {response.read()}"
                else:
                    print("Weather information is not available at the moment.")
                    return ""
        except urllib.error.URLError as e:
            print(f"Failed to get weather information: {e.reason}")
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
            print("Image uploaded successfully to FreeImage.host!")
            return file_url

        except Exception as e:
            print(f"Failed to upload image to FreeImage.host: {e}")
            return ""

    def is_image_generation_request(self, request):
        """Check if the request is asking for image generation"""
        image_keywords = [
            "generate an image",
            "create an image",
            "make an image",
            "draw a picture",
            "create a picture",
            "generate a picture",
            "make a picture",
            "show me a picture",
            "show me an image",
            "create a visual",
            "generate a visual",
            "make a visual"
        ]
        return any(keyword in request.lower() for keyword in image_keywords)

    def generate_image(self, prompt):
        """Generate an image using the appropriate service"""
        try:
            if self.ai_service == "google":
                # Use Gemini's image generation
                response = self.llm.models.generate_content(
                    model="gemini-2.0-flash-exp-image-generation",
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
                    model="dall-e-3",
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
            print(f"Error generating image: {e}")
            return None

    def send_to_chat_gpt(self, request, image=None, image_link=''):
        modelToUse = self.model
        image_url = ''
        image_format = 'image/jpeg'
        emptyRequest = request == ''
        defaultImageRequest = 'Describe this image.'
        # replace the timestamp in the history with the current time
        current_time = datetime.now(get_localzone()).strftime('%I:%M %p %Z').lstrip("0")
        if self.history and self.history[0]["role"] == "system":
            self.history[0]["content"] = self.history[0]["content"].replace("{today}", str(date.today())).replace("{theCurrentTime}", current_time)
        
        # Check if this is an image generation request
        if self.is_image_generation_request(request):
            canned_response = "Here is the image you wanted - "
            self.append2log(f"\n\n{self.assistant_name}: {canned_response}", True)
            
            # Generate the image
            image_data = self.generate_image(request)
            if image_data:
                generated_image_filename = "generated_image.png"
                # Store the image based on configuration
                if self.image_storage == "freeimage":
                    image_url = self.upload_image_to_freeimage(image_data, generated_image_filename)
                else:
                    upload_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.upload_folder)
                    if not os.path.exists(upload_path):
                        os.makedirs(upload_path)

                    generated_image_filename = f"{time.time()}_{os.path.basename(generated_image_filename)}"
                    safe_file_name = os.path.join(upload_path, generated_image_filename)
                    #save image to local file
                    with open(safe_file_name, "wb") as f:
                        f.write(image_data)
                    image_url = f"http://{self.host}:{self.port}/{self.upload_folder}/{generated_image_filename}"
                
                # Add the image URL to the chat log
                self.append2log(f"{image_url}\n\n", True)
                return [canned_response]
            else:
                return ["I apologize, but I couldn't generate the image you requested."]

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
                modelToUse = self.groq_vision_model
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
            #print(self.history)
            print(f"Sending to {self.ai_service} {modelToUse}...")
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
                    # Create a chat for text-only conversations
                    chat = self.llm.chats.create(model=modelToUse, config=types.GenerateContentConfig(system_instruction=system_prompt))
                    
                    # Add previous messages to chat history, if any
                    if len(self.history) > 1:
                        for msg in self.history[1:-1]:  # Skip system message and latest user message
                            if msg["role"] == "user":
                                chat.send_message(msg["content"])
                    # Send the current message and stream the response
                    response = chat.send_message_stream(self.history[-1]["content"])
                    print(f"Response: {response}")
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
            print(result + str(e))
            return result
        
        def text_iterator():
            response_full_text = ""
            sentence = ""
            sentence_endings = {'.', '!', '?'}
            self.append2log(f"{self.assistant_name}: ", True)
            
            if self.ai_service == "google":
                # Process Google Gemini response stream
                for chunk in response:
                    if hasattr(chunk, 'text') and chunk.text:
                        text_content = chunk.text
                        sentence += text_content.replace('\n', ' ')
                        response_full_text += text_content.replace('\n', ' ')
                        # Check if the current text ends with sentence ending
                        if text_content and text_content[-1] in sentence_endings:
                            self.append2log(sentence, True)
                            yield sentence
                            sentence = ""
            else:
                # Process OpenAI/Groq response stream
                for chunk in response:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        sentence += delta.content.replace('\n', ' ')
                        response_full_text += delta.content.replace('\n', ' ')
                        # Check if the current character ends the sentence
                        if delta.content[-1] in sentence_endings:
                            self.append2log(sentence, True)
                            yield sentence
                            sentence = ""
                            
            # Yield any remaining text after the loop ends
            if sentence:
                self.append2log(sentence)
                yield sentence
            else:
                self.append2log("")
            self.history.append({"role": "assistant", "content": response_full_text})
        
        return text_iterator()
