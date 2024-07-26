@echo off
:: Define the name of the zip file
set ZIP_FILE=dist\jarvis_chatbot.zip

:: Remove any existing zip file with the same name
if exist %ZIP_FILE% del %ZIP_FILE%

:: Create a zip file containing the executable and necessary files
powershell Compress-Archive -Path dist\jarvis_chatbot\* -DestinationPath %ZIP_FILE%

echo Project has been packaged into %ZIP_FILE%