#import os
#from os import environ
#environ['OPENAI_LOG'] = 'debug'
import base64
import openai
from groq import Groq
import urllib
import geocoder
import time
from datetime import date, datetime
import requests
from tzlocal import get_localzone
import os

class ChatGPTService:
    def __init__(self, config):
        self.append2log = None
        self.use_groq = config["use_groq"]
        if (self.use_groq):
            self.model = config["groq_model"]
            self.groq_vision_model = config["groq_vision_model"]
            self.llm = Groq(api_key=config["groq_key"])
        else:
            openai.api_key = config["openai_key"]
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
        self.use_freeimage_host = config["use_freeimage_host"]
        self.freeimage_key = config["freeimage_key"]


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
                # Map common file extensions to MIME types
                mime_map = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp',
                    '.bmp': 'image/bmp'
                }
                # Get file extension from filename
                ext = os.path.splitext(filename)[1].lower()
                mime_type = mime_map.get(ext, 'image/jpeg')  # Default to jpeg if unknown extension
                
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


    def send_to_chat_gpt(self, request, image=None, image_link=''):
        modelToUse = self.model
        image_url = ''
        # replace the timestamp in the history with the current time
        current_time = datetime.now(get_localzone()).strftime('%I:%M %p %Z').lstrip("0")
        if self.history and self.history[0]["role"] == "system":
            self.history[0]["content"] = self.history[0]["content"].replace("{today}", str(date.today())).replace("{theCurrentTime}", current_time)
        
        if image is not None:
            if self.use_freeimage_host:
                image_url = self.upload_image_to_freeimage(image, image_link)
            else:                
                image_url = f"data:image/jpeg;base64,{base64.b64encode(image).decode('utf-8')}"

            if image_link != '':
                if request == '':
                    request = 'Describe this image.'
                content = [{"type": "text", "text": "respond as concisely as possible to the following request: " + request}, {"type": "image_url", "image_url": {"url": image_url}}]
            else:
                return None

            if self.use_groq:
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
            print(self.history)
            response = self.llm.chat.completions.create(
                model=modelToUse, 
                messages=self.history,
                temperature=0.7,
                stream=True
            )

            self.append2log(f" {image_url} \n\n", True)
        
        except Exception as e:
            result = "Unknown Error "
            print(result + str(e))
            return result
        
        def text_iterator():
            response_full_text = ""
            sentence = ""
            sentence_endings = {'.', '!', '?'}
            #print(f"{self.assistant_name}: ", end="")
            self.append2log(f"{self.assistant_name}: ", True)
            for chunk in response:
                delta = chunk.choices[0].delta
                if delta.content:
                    sentence += delta.content.replace('\n', ' ')
                    response_full_text += delta.content.replace('\n', ' ')
                    # Check if the current character ends the sentence
                    if delta.content[-1] in sentence_endings:
                        #print(sentence, end="")
                        self.append2log(sentence, True)
                        yield sentence
                        sentence = ""
            # Yield any remaining text after the loop ends
            if sentence:
                #print(sentence)
                self.append2log(sentence)
                yield sentence
            else:
                self.append2log("")
            self.history.append({"role": "assistant", "content": response_full_text})
        
        return text_iterator()
