@echo off

:: Activate the virtual environment
call venv\Scripts\activate.bat

:: Run the application
python main.py

:: Deactivate the virtual environment when done
call venv\Scripts\deactivate.bat 