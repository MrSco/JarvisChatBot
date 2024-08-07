@echo off

:: install mpv and vlc with chocolatey
choco install mpv vlc -y

:: Check for Python 3
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Python 3 could not be found. Please install Python 3.
    exit /b 1
)

:: Check for pip
pip --version > nul 2>&1
if %errorlevel% neq 0 (
    echo pip for Python 3 could not be found. Please install pip.
    exit /b 1
)

:: Create a virtual environment
python -m venv venv

:: Activate the virtual environment
call venv\Scripts\activate.bat

:: Install requirements
pip install -r requirements-win.txt

echo Setup completed successfully.