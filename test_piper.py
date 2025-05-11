import subprocess
import tempfile
import os

def speak_text(text):
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as temp_file:
        # get path of the file  
        temp_path = temp_file.name
        print(f"Using temporary file: {temp_path}")
    
    print(f"Starting Piper... (output to {temp_path})")
    # Start piper process with file output
    p1 = subprocess.Popen(
        ['./piper/piper.exe', '--model', 'piper_models/jarvis.onnx', '--output-file', temp_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    print("Sending text to Piper...")
    # Send text to piper and close stdin
    p1.stdin.write(f'{text}\n'.encode())
    p1.stdin.flush()
    p1.stdin.close()

    print("Waiting for Piper to finish...")
    # Wait for Piper to finish generating
    while True:
        line = p1.stderr.readline().decode()
        if not line:
            print("Piper stderr closed unexpectedly")
            break
        print(f"Piper: {line.strip()}")
        if "Real-time factor" in line:
            print("Found completion signal!")
            break

    print("Playing audio...")
    # Play the wav file with mpv
    p2 = subprocess.run(
        ['mpv', '--no-video', temp_path]
    )

    # Clean up the temporary file
    os.unlink(temp_path)
    print("Done!")

# Test the function
speak_text("Hello world, this is a test of the temporary file approach.")


