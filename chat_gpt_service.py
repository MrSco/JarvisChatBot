#import os
#from os import environ
#environ['OPENAI_LOG'] = 'debug'
import openai
from groq import Groq
import urllib
import geocoder
import time
from datetime import date
import requests

class ChatGPTService:
    def __init__(self, config):
        self.append2log = None
        self.use_groq = config["use_groq"]
        if (self.use_groq):
            self.model = config["groq_model"]
            self.llm = Groq(api_key=config["groq_key"])
        else:
            openai.api_key = config["openai_key"]
            self.model = config["openai_model"]
            self.llm = openai
        self.assistant_name = config["assistant_dict"]["name"]
        self.assistant_acronym = config["assistant_dict"]["acronym"]
        self.assistant_descr = config["assistant_dict"]["descr"]
        self.system_prompt = config["system_prompt"]
        self.weather_info = self.get_weather_url()
        today = str(date.today()) 
        self.system_prompt = config["system_prompt"] \
            .replace("{assistant_name}", self.assistant_name) \
            .replace("{assistant_acronym}", self.assistant_acronym) \
            .replace("{assistant_descr}", self.assistant_descr) \
            .replace("{today}", today) \
            .replace("{theCurrentTime}", time.strftime('%I:%M %p').lstrip("0")) \
            .replace("{weather_info}", self.weather_info)
        self.history = [{"role": "system", "content": self.system_prompt}]
        self.sound_effect = None
        self.imgur_client_id = config["imgur_client_id"]
        self.use_imgur = config["use_imgur"]

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
        
    def upload_image_to_imgur(self, image_data):
        url = "https://api.imgur.com/3/image"
        headers = {
            "Authorization": f"Client-ID {self.imgur_client_id}"
        }
        payload = {
            "image": image_data,
            "type": "base64"
        }
        print("Uploading image to imgur...")
        #print(image_data)
        response = requests.post(url, headers=headers, data=payload)
        link = ''
        if response.status_code == 200:
            data = response.json()
            print("Image uploaded successfully!")
            link = data['data']['link']
            print("Link to the image:", link)
        else:
            print("Failed to upload image. Status code:", response.status_code)
            # Detailed request printing
            # request_details = f"Method: {response.request.method}\n" \
            #                 f"URL: {response.request.url}\n" \
            #                 f"Headers: {response.request.headers}\n" \
            #                 f"Body: {response.request.body.decode('utf-8') if response.request.body else 'No body'}"
            # print(f"Request details:\n{request_details}")
            print("Response:", response.json())
        return link

    def send_to_chat_gpt(self, request, image=None, image_link=''):
        start_time = time.time()
        if not self.use_groq and image is not None:
            if self.use_imgur:
                image_link = self.upload_image_to_imgur(image)
                image_url = image_link
            else:
                image_url = f"data:image/jpeg;base64,{image}"
            if image_link != '':
                content = [{"type": "text", "text": request}, {"type": "image_url", "image_url": {"url": image_url}}]
            else:
                return None
        else:
            content = request
        self.history.append({"role": "user", "content": content})
        result = None
        try:
            #print(self.history)
            response = self.llm.chat.completions.create(
                model=self.model, 
                messages=self.history,
                max_tokens=300,
                temperature=1,
                stream=True
            )
        except Exception as e:
            result = "Unknown Error "
            print(result + str(e))
            return result
        
        self.append2log(f" {image_link} \n\n", True)

        def text_iterator():
            response_full_text = ""
            sentence = ""
            sentence_endings = {'.', '!', '?'}
            #print(f"{self.assistant_name}: ", end="")
            self.append2log(f"{self.assistant_name}: ", True)
            for chunk in response:
                delta = chunk.choices[0].delta
                if delta.content:
                    sentence += delta.content.replace('\n', '')
                    response_full_text += sentence
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
            end_time = time.time()
            print(f"Time taken: {end_time - start_time} seconds")
            self.history.append({"role": "assistant", "content": response_full_text})
        
        return text_iterator()
