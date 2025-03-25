@echo off

:: install mpv and vlc with chocolatey
choco install mpv vlc -y

:: Create a virtual environment
python -m venv venv

:: Activate the virtual environment
call venv\Scripts\activate.bat

:: Install requirements
pip install -r requirements.txt

:: check if config.json exists and if not, copy config.json.example to config.json
if not exist config.json (
    echo config.json does not exist, copying config.json.example to config.json
    copy config.json.example config.json
    echo Please edit config.json and add your API keys and other configuration.
)

:: check if assistants.json exists and if not, copy assistants.json.example to assistants.json
if not exist assistants.json (
    echo assistants.json does not exist, copying assistants.json.example to assistants.json
    copy assistants.json.example assistants.json
)

echo Setup completed successfully. You can now run the script with ./run.bat
