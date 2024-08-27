#!/bin/bash

# Check for Python 3
if ! command -v python3 &> /dev/null
then
    echo "Python 3 could not be found. Please install Python 3."
    exit 1
fi

# Check for pip
if ! command -v pip3 &> /dev/null
then
    echo "pip for Python 3 could not be found. Please install pip."
    exit 1
fi

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# For Windows, use venv\Scripts\activate instead
source venv/bin/activate

#update pip
pip install --upgrade pip

# Install requirements
pip3 install -r requirements.txt

echo "Setup completed successfully."