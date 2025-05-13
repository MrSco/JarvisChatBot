import re
import subprocess
import time
import platform
import json  # Add json import for parsing MPV output

is_rpi = platform.system() == "Linux"  # Check if running on RPi

def init_piper():
    print("Starting Piper process...")
    # Start piper process with raw output
    p1 = subprocess.Popen(
        ['./piper/piper' if is_rpi else './piper/piper.exe', '--model', 'piper_models/jarvis.onnx', '--output-raw'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )    
    
    return p1

def init_mpv(piper_process):
    print("Starting MPV process...")
    mpv_process = subprocess.Popen(
        [
            'mpv',
            '--no-video',
            '--demuxer=rawaudio',
            '--demuxer-rawaudio-rate=22050',
            '--demuxer-rawaudio-format=s16le',
            '--demuxer-rawaudio-channels=1',
            '--audio-channels=mono',
            '--audio-samplerate=22050',
            '--audio-buffer=0.1',
            '--ao=alsa' if is_rpi else '',
            '-'
        ],
        stdin=piper_process.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return mpv_process

def speak_text(piper_process, mpv_process, text):
    print(f"\nSpeaking: {text}")
    
    # Send text to piper
    print("Sending text to Piper...")
    piper_process.stdin.write(f'{text}\n'.encode())
    piper_process.stdin.flush()

    print("Waiting for Piper to finish...")
    # Wait for Piper to finish generating
    while True:
        line = piper_process.stderr.readline().decode()
        if not line:
            print("Piper stderr closed unexpectedly")
            break
        print(f"Piper: {line.strip()}")
                    
        if "Real-time factor" in line:
            print("Found completion signal!")
            break
    
    # Wait for MPV to finish playing the current phrase
    print(f"Starting playback...")
    start_time = time.time()

    while True:        
        # Check MPV's stderr for status
        line = mpv_process.stderr.readline()
        line = line.strip()
        print(f"MPV stderr: {line}")
        
        # parse out percentage from mpv status line 'MPV stderr: A: 00:00:05 / 00:00:05 (100%)'
        if "%)" in line:
            percentage = line.split("(")[1].split(")")[0].split("%")[0].strip()
            print(f"Current percentage: {percentage}")
            if percentage == "100":
                print("Playback likely complete")
                break

        if time.time() - start_time > 30:
            print("Timeout waiting for playback")
            break
            
        time.sleep(0.01)  # Small sleep to prevent busy waiting

print("Initializing piper process...")
piper_process = init_piper()
print("Initializing MPV process...")
mpv_process = init_mpv(piper_process)

try:
    # Test multiple phrases
    phrases = [
        "Ten",
        "This is the second phrase, using the same Piper process.",
        "This is the third phrase.",
        "Four",
        "And finally, here is a really long phrase that should take more than 5 seconds to play. Good luck!"
    ]
    
    for i, phrase in enumerate(phrases, 1):
        print(f"\nPhrase {i} of {len(phrases)}")
        speak_text(piper_process, mpv_process, phrase)
        
finally:
    # Clean up
    print("\nCleaning up...")
    if piper_process.stdin:
        try:
            piper_process.stdin.close()
        except:
            pass
    if mpv_process:
        try:
            mpv_process.terminate()
            mpv_process.wait(timeout=2)
        except:
            try:
                mpv_process.kill()
            except:
                pass
    try:
        piper_process.terminate()
        piper_process.wait(timeout=2)
    except:
        piper_process.kill()
    print("Done!")


