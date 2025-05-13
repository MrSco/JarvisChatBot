import re
import subprocess
import time
import platform
import json  # Add json import for parsing MPV output
import threading
import queue
import select
import os

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
            '--ao=alsa' if is_rpi else '',
            '-'
        ],
        stdin=piper_process.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return mpv_process

def mpv_stderr_reader(mpv_process, queue, stop_event):
    """Read MPV stderr output in a separate thread"""
    while not stop_event.is_set():
        try:
            line = mpv_process.stderr.readline()
            if not line:
                time.sleep(0.01)  # Small sleep if no data
                continue
                
            # Split the line by any status updates (they start with 'A: ')
            parts = line.strip().split('A: ')
            for part in parts:
                if part:  # Skip empty parts
                    if not part.startswith('A: '):
                        part = 'A: ' + part
                    queue.put(part)
        except Exception as e:
            print(f"Error reading MPV stderr: {e}")
            time.sleep(0.01)

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
    
    # Set up MPV stderr reading thread
    mpv_queue = queue.Queue()
    stop_event = threading.Event()
    stderr_thread = threading.Thread(
        target=mpv_stderr_reader,
        args=(mpv_process, mpv_queue, stop_event),
        daemon=True
    )
    stderr_thread.start()
    
    # Wait for MPV to finish playing the current phrase
    print(f"Starting playback...")
    start_time = time.time()
    last_percentage = 0
    
    try:
        while True:
            # Check if we've exceeded timeout (30 seconds)
            if time.time() - start_time > 30:
                print("Timeout reached waiting for playback")
                break
                
            try:
                # Try to get a line from the queue with a timeout
                line = mpv_queue.get(timeout=0.01)
                if not line.strip():  # Skip empty lines
                    continue
                    
                print(f"MPV stderr: {line}")
                
                # parse out percentage from mpv status line
                if "%)" in line:
                    try:
                        percentage = int(line.split("(")[1].split(")")[0].split("%")[0].strip())
                        if percentage > last_percentage:  # Only print if percentage increased
                            print(f"Current percentage: {percentage}")
                            last_percentage = percentage
                        if percentage == 100:
                            print("Playback complete")
                            # Wait a small amount to ensure audio is fully played
                            time.sleep(0.1)
                            break
                    except (IndexError, ValueError) as e:
                        print(f"Error parsing percentage: {e}")
                        continue
            except queue.Empty:
                # No output available, continue waiting
                continue
                
            time.sleep(0.01)  # Small sleep to prevent busy waiting
    finally:
        # Signal the reader thread to stop
        stop_event.set()
        # Wait a brief moment for the thread to finish
        stderr_thread.join(timeout=0.5)

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
        "And finally, here is a really long phrase that should take more than 5 seconds to play. Good luck, you're gonna need it. I'd buy that for a dollar!"
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


