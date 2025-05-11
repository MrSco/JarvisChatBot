import subprocess
import os
import time

def init_piper():
    print("Starting Piper process...")
    # Start piper process with raw output
    p1 = subprocess.Popen(
        ['./piper/piper.exe', '--model', 'piper_models/jarvis.onnx', '--output-raw'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Start mpv process that will stay running
    print("Starting MPV process...")
    p2 = subprocess.Popen(
        [
            'mpv',
            '--no-video',
            '--demuxer=rawaudio',
            '--demuxer-rawaudio-rate=22050',
            '--demuxer-rawaudio-format=s16le',
            '--demuxer-rawaudio-channels=1',
            '--audio-channels=mono',
            '--audio-samplerate=22050',
            '--term-status-msg=status: ${=time-pos}',  # Output current playback position
            '--term-playing-msg=started',              # Message when playback starts
            '--term-status-msg=ended',                 # Message when playback ends
            '-'
        ],
        stdin=p1.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,  # Use text mode for easier reading
        bufsize=1   # Line buffered
    )
    
    # Allow p1 to receive a SIGPIPE if p2 exits
    p1.stdout.close()
    
    return p1, p2

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
    
    # Wait for MPV to finish playing
    print("Waiting for playback to complete...")
    while True:
        # Check MPV's stderr for status
        line = mpv_process.stderr.readline()
        print(f"MPV err: {line.strip()}")
        if "ended" in line.strip():
            print("Playback complete!")
            break
        
        time.sleep(0.1)  # Small sleep to prevent busy waiting

print("Initializing processes...")
piper_process, mpv_process = init_piper()

try:
    # Test multiple phrases
    phrases = [
        "Hello! This is a test of the first phrase.",
        "This is the second phrase, using the same Piper process.",
        "And finally, this is the third phrase."
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
    try:
        piper_process.terminate()
        piper_process.wait(timeout=2)
        mpv_process.terminate()
        mpv_process.wait(timeout=2)
    except:
        piper_process.kill()
        mpv_process.kill()
    print("Done!")


