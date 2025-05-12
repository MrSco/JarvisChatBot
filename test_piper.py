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

def speak_text(piper_process, text, previous_total_duration=0):
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
                'ao=alsa' if is_rpi else ''
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
    total_audio_duration = 0
    # Wait for Piper to finish generating
    while True:
        line = piper_process.stderr.readline().decode()
        if not line:
            print("Piper stderr closed unexpectedly")
            break
        print(f"Piper: {line.strip()}")
        if "Real-time factor" in line:
            # extract the total cumulative duration from the line and round down to nearest half second
            total_audio_duration = round(float(line.split("audio=")[1].split(" ")[0].split("e")[0]) * 2) / 2
            # Calculate actual duration for this phrase
            current_phrase_duration = total_audio_duration - previous_total_duration
            print(f"Total cumulative duration: {total_audio_duration} seconds")
            print(f"Current phrase duration: {current_phrase_duration} seconds")
            print("Found completion signal!")
            break
    
    # Wait for MPV to finish playing the current phrase duration
    print("Waiting for playback to complete...")
    start_time = time.time()
    while time.time() - start_time < current_phrase_duration:
        # Check MPV's stderr for status
        line = mpv_process.stderr.readline()
        if any(signal in line for signal in ["EOF", "Audio device underrun detected"]):
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
    
    return total_audio_duration  # Return the total duration for the next call

print("Initializing piper process...")
piper_process = init_piper()

try:
    # Test multiple phrases
    phrases = [
        "Ten.",
        "This is the second phrase, using the same Piper process.",
        "This is the third phrase.",
        "One"
    ]
    
    cumulative_duration = 0
    for i, phrase in enumerate(phrases, 1):
        print(f"\nPhrase {i} of {len(phrases)}")
        cumulative_duration = speak_text(piper_process, phrase, cumulative_duration)
        
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


