from io import BytesIO
import logging
import requests
import re
import cv2
import numpy as np
from PIL import Image
from image2sand import Image2Sand
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

class DuneWeaver:
    def __init__(self, config):
        # Initialize DuneWeaver support
        self.duneweaver_url = config.get("duneweaver_url", "")
        self.dw_prompt = config.get("dw_prompt", "")
        self.image2sand = Image2Sand()

    def is_duneweaver_request(self, request):
        """Check if the request is asking for image generation that we can send to Dune Weaver"""
        image_keywords = [
            "weave a image",
            "weave an image",
            "weave a picture",
            "weave a drawing",
            "weave a painting",
            "weave a sketch",
            "weave a photo",
            "weave a photograph",
            "weave an picture",
            "weave an drawing",
            "weave an painting",
            "weave an sketch",
            "weave an photo",
            "weave an photograph",
            "draw on the sand",
            "draw on the sand an image",
            "draw on the sand an picture",
            "draw on the sand an drawing",
            "draw on the sand an painting",
            "draw on the sand an sketch",
            "draw on the sand an photo",
            "draw on the sand an photograph",
            "draw on the sand a image",
            "draw on the sand a picture",
            "draw on the sand a drawing",
            "draw on the sand a painting",
            "draw on the sand a sketch",
            "draw on the sand a photo",
            "draw on the sand a photograph",
            "stop execution",
            "stop the execution",
            "stop the weaving",
            "stop the drawing",
            "stop the painting",
            "stop the sketch",
            "stop the photo",
            "stop the photograph",
            "stop duneweaver",
            "stop duneweaver execution",
            "stop duneweaver weaving",
            "stop duneweaver drawing",
            "stop duneweaver painting",
            "stop duneweaver sketch",
            "stop duneweaver photo",
        ]
        return any(keyword in request.lower() for keyword in image_keywords)
    
    def extract_draw_prompt(self, text: str):
        """Extract the drawing prompt from the transcribed text"""
        text = text.lower()
        prompt = None
        # using a regex, check for weave, draw, create, make, generate, etc.
        # capture the keyword and everything after it except for the image, picture, drawing, painting, sketch, photo, photograph and 'of'
        match = re.search(r"\b(?:weave|draw|create|make|generate)\b\s+(?:an|a)\s+(?:image|picture|drawing|painting|sketch|photo|photograph)(?:\s+of\s+(.+))?", text)
        if match:
            prompt = match.group(1).strip()  # Get the content after the command and strip whitespace
        else:
            prompt = text.strip()
            
        # Strip articles like "a", "an", "the" from the beginning of the prompt
        prompt = re.sub(r"^\s*(a|an|the)\s+", "", prompt)
        logger.info(f"Extracted duneweaver draw prompt: {prompt}")
        return prompt

    def convert_image_to_sand_pattern(self, image_data):
        """Convert an image to sand table coordinates using Image2Sand"""
        if not self.image2sand:
            logger.error("Image2Sand not initialized - DuneWeaver URL was not configured")
            return None
            
        try:
            logger.info(f"Converting image to sand pattern")
            img = Image.open(BytesIO(image_data))

            # Convert PIL Image to OpenCV format (numpy array)
            img_array = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            
            # Configure options for sand pattern generation
            options = {
                'epsilon': 0.5,  # Controls point density
                'contour_mode': 'Tree',  # Use tree mode for better pattern detection
                'is_loop': True,  # Create continuous patterns
                'minimize_jumps': True,  # Optimize path to minimize jumps
                'output_format': 2,  # Use .thr format for Dune Weaver
                'max_points': 300  # Limit number of points for smooth operation
            }
            
            # Process the image and generate coordinates
            result = self.image2sand.process_image(img_array, options)
            
            return result.get('formatted_coords')
        except Exception as e:
            logger.error(f"Error converting image to sand pattern: {e}")
            return None

    def list_theta_rho_files(self):
        """ Do a GET request to the theta_rho API with a 5 second timeout """
        url = f"{self.duneweaver_url}/list_theta_rho_files"
        response = None
        try:
            logger.info(f"Listing theta_rho files from {url}")
            response = requests.get(url, timeout=5).json()
        except Exception as e:
            logger.error(f"Error listing theta_rho files: {e}")
        finally:
            return response
    
    def upload_theta_rho(self, pattern_path: str):
        """ Do a POST request to the theta_rho API """
        url = f"{self.duneweaver_url}/upload_theta_rho"
        response = None
        with open(pattern_path, 'rb') as f:
            files = {'file': f}
            try:
                logger.info(f"Uploading theta_rho file {pattern_path} to {url}")
                response = requests.post(url, files=files, timeout=5).json()
            except Exception as e:
                logger.error(f"Error uploading theta_rho: {e}")
                response = {"detail": str(e)}
            finally:
                return response
    
    def run_theta_rho(self, pattern_path: str):
        """ Do a POST request to the theta_rho API """
        url = f"{self.duneweaver_url}/run_theta_rho"
        response = None
        data = {
            'file_name': pattern_path,
            'pre_execution': 'adaptive'
        }
        logger.info(f"Running theta_rho with data: {data}")
        try:
            response = requests.post(url, json=data, timeout=5).json()
        except Exception as e:
            logger.error(f"Error running theta_rho: {e}")
            response = {"detail": str(e)}
        finally:
            return response
    
    def stop_execution(self):
        url = f"{self.duneweaver_url}/stop_execution"
        logger.info(f"Stopping DuneWeaver execution...")
        response = None
        try:
            response = requests.post(url, timeout=5).json()
        except Exception as e:
            logger.error(f"Error stopping DuneWeaver execution: {e}")
            response = {"detail": str(e)}
        finally:
            return response
