import re
import subprocess
import time
import platform

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

def speak_text(piper_process, text):
    print(f"\nSpeaking: {text}")

    # Start mpv process that will stay running
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
            '--term-status-msg=time-remaining/full: ${time-remaining/full}',
            '-'
        ],
        stdin=piper_process.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,  # Use text mode for easier reading
    )
    
    # Send text to piper
    print("Sending text to Piper...")
    piper_process.stdin.write(f'{text}\n'.encode())
    piper_process.stdin.flush()

    print("Waiting for Piper to finish...")
    piper_start_time = time.time()
    piper_finish_time = None
    # Wait for Piper to finish generating
    while True:
        line = piper_process.stderr.readline().decode()
        if not line:
            print("Piper stderr closed unexpectedly")
            break
        print(f"Piper: {line.strip()}")
                    
        if "Real-time factor" in line:
            # extract the duration from the line 
            raw_duration = float(line.split("audio=")[1].split(" ")[0].split("e")[0])
            print(f"Raw audio duration: {raw_duration} seconds")
            print("Found completion signal!")
            break
    piper_finish_time = time.time()
    # Add padding if needed to ensure 0.5s gap since Piper finished
    time_since_generation = piper_finish_time - piper_start_time
    print(f"Time since generation: {time_since_generation:.2f} seconds")
    if time_since_generation < 0.5:
        padding_needed = 0.5 - time_since_generation
        print(f"Adding {padding_needed:.2f}s pause before playback")
        time.sleep(padding_needed)
    
    # Wait for MPV to finish playing the current phrase duration
    print(f"Starting playback...")
    start_time = time.time()
    initial_duration = None  # To store the first time remaining estimate

    while True:        
        # Check MPV's stderr for status
        line = mpv_process.stderr.readline()
        print(f"MPV stderr: {line.strip()}")
        
        # parse out the time remaining
        time_remaining = re.search(r'time-remaining/full: (-?\d{2}:\d{2}:\d{2}\.\d{3})', line)
        if time_remaining:
            # Convert HH:MM:SS.mmm format to seconds, handling negative values. negative means its definitely done playing and we can break
            ts = time_remaining.group(1)
            is_negative = ts.startswith('-')
            if is_negative:
                break
            h, m, s = ts.split(':')
            total_seconds = float(h) * 3600 + float(m) * 60 + float(s)
            print(f"Time remaining: {total_seconds} seconds")
            
            # Capture initial duration estimate
            if initial_duration is None:
                initial_duration = total_seconds
                print(f"Initial duration estimate: {initial_duration} seconds")
            
            # Break if time remaining is very low or if we've exceeded the initial estimate
            if total_seconds <= 0.1 or (initial_duration and (time.time() - start_time) >= initial_duration + 0.5):
                print(f"Time elapsed: {time.time() - start_time} seconds")
                print(f"Playback complete! by {line.strip()}")
                break
            
        time.sleep(0.1)  # Small sleep to prevent busy waiting

    try:
        mpv_process.terminate()
        mpv_process.wait(timeout=2)
        print("MPV process stopped")
    except Exception as e:
        print(f"Error stopping MPV process: {e}")
        try:
            mpv_process.kill()
        except:
            pass
    mpv_process = None

print("Initializing piper process...")
piper_process = init_piper()

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
        speak_text(piper_process, phrase)
        
finally:
    # Clean up
    print("\nCleaning up...")
    if piper_process.stdin:
        try:
            piper_process.stdin.close()
        except:
            pass
    try:
        piper_process.terminate()
        piper_process.wait(timeout=2)
    except:
        piper_process.kill()
    print("Done!")


