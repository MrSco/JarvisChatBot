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

# check if piper is installed
if ! command -v piper &> /dev/null; then
    # download piper binary and add it to the PATH
    curl -L https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz -o piper_arm64.tar.gz

    # extract the binary
    tar -xvzf piper_arm64.tar.gz

    # remove the tar.gz file
    rm piper_arm64.tar.gz

    # add line export PATH="$PATH:$HOME/piper" to the bottom of the .bashrc file
    echo "export PATH=\"$PATH:$HOME/piper\"" >> ~/.bashrc

    # reload the .bashrc file
    source ~/.bashrc
fi

# check if config.json exists and if not, copy config.json.example to config.json
if [ ! -f config.json ]; then
    echo "config.json does not exist, copying config.json.example to config.json"
    cp config.json.example config.json
    echo "Please edit config.json and add your API keys and other configuration."
fi

# check if assistants.json exists and if not, copy assistants.json.example to assistants.json
if [ ! -f assistants.json ]; then
    echo "assistants.json does not exist, copying assistants.json.example to assistants.json"
    cp assistants.json.example assistants.json
fi

echo "Setup completed successfully. You can now run the script with ./run.sh"