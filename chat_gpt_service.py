#import os
#from os import environ
#environ['OPENAI_LOG'] = 'debug'
import openai
from openai import OpenAI
import urllib
import geocoder
import time
from datetime import date
import requests

class ChatGPTService:
    def __init__(self, config):
        self.append2log = None
        self.emit_update_chat = None
        openai.api_key = config["openai_key"]
        self.openai_async = OpenAI(api_key=config["openai_key"])
        self.assistant_name = config["assistant_name"]
        self.system_prompt = config["system_prompt"]
        self.openai_model = config["openai_model"]
        self.weather_info = self.get_weather_url()
        today = str(date.today()) 
        self.system_prompt = config["system_prompt"].replace("{assistant_name}", self.assistant_name).replace("{today}", today).replace("{theCurrentTime}", time.strftime('%I:%M %p').lstrip("0")).replace("{weather_info}", self.weather_info)
        self.history = [{"role": "system", "content": self.system_prompt}]
        self.sound_effect = None
        self.stream_responses = config["stream_responses"]
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
        if image is not None:
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
            response = openai.chat.completions.create(
                model=self.openai_model, 
                messages=self.history,
                max_tokens=300,
                temperature=1,
                stream=self.stream_responses
            )
            if not self.stream_responses:                
                result = response.choices[0].message.content
                end_time = time.time()
        except openai.APIConnectionError as e:
            result = "API Connection Error: "
            print(result + str(e))
            return result
        except openai.RateLimitError as e:
            result = "Rate Limit Error: "
            print(result + str(e))
            return result
        except openai.APIError as e:
            result = "API Error: "
            print(result + str(e))
            return result
        except Exception as e:
            result = "Unknown Error "
            print(result + str(e))
            return result
        
        if not self.stream_responses:
            if result is None:
                return None
        
        def wrapUp(result):
            self.history.append({"role": "assistant", "content": result})
            self.append2log(f" {image_link} \n\n", True)
            self.emit_update_chat(f"You: {request} {image_link}")
            self.append2log(f"{self.assistant_name}: {result}")

        def text_iterator():
            response_full_text = ""
            #self.append2log(f"{self.assistant_name}: ") 
            for chunk in response:
                delta = chunk.choices[0].delta
                if delta.content:
                    response_full_text += delta.content
                    yield delta.content
            end_time = time.time()
            print(f"Time taken: {end_time - start_time} seconds")
            wrapUp(response_full_text) 
            print(f"{self.assistant_name}: {response_full_text}")
        
        if self.stream_responses:
            return text_iterator()
        end_time = time.time()
        print(f"Time taken: {end_time - start_time} seconds")
        wrapUp(result)
        return str.strip(result)
