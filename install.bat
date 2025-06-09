@echo off

:: install mpv and vlc with chocolatey
choco install python311 mpv vlc -y

:: Create a virtual environment
python -m venv venv
echo virtual environment created

:: Activate the virtual environment
call venv\Scripts\activate.bat

:: Install piper-phonemize
:: https://github.com/rhasspy/piper-phonemize/issues/34
pip install https://github.com/Marc56K/piper-phonemize-win32/releases/download/v1.2.1/piper_phonemize-1.2.1-cp311-cp311-win_amd64.whl

:: Install requirements
pip install -r requirements.txt

:: check if piper is installed
if not exist piper\piper.exe (
    :: download piper binary
    curl -L https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip -o piper_windows_amd64.zip

    :: extract the binary
    tar -xvzf piper_windows_amd64.zip

    :: remove the zip file
    del piper_windows_amd64.zip

)
echo piper binary installed

:: check if vasco model is downloaded already
if not exist piper_models\vasco.onnx (
    echo vasco.onnx does not exist, downloading the model
    :: download the model
    curl -L https://huggingface.co/poisson-fish/piper-vasco/blob/main/onnx/vasco.tar.gz -o piper_models\vasco.tar.gz

    :: extract the model
    tar -xvzf piper_models\vasco.tar.gz -C piper_models

    :: remove the tar.gz file
    del piper_models\vasco.tar.gz
)

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

:: create .setup_complete file
echo Setup completed on %date% %time% > .setup_complete

echo Setup completed successfully. You can now run the script with ./run.bat
