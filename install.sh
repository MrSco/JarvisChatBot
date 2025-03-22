#!/bin/bash


# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# For Windows, use venv\Scripts\activate instead
source venv/bin/activate

#update pip
pip3 install --upgrade pip

# Install requirements
pip3 install -r requirements.txt

echo "Setup completed successfully."