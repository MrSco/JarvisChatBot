@echo off

:: install mpv and vlc with chocolatey
choco install mpv vlc -y

:: Create a virtual environment
python -m venv venv

:: Activate the virtual environment
call venv\Scripts\activate.bat

:: Install requirements
pip install -r requirements.txt

echo Setup completed successfully.