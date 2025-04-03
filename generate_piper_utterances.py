import subprocess
import argparse
from pathlib import Path

# Standard utterances used across all assistants
STANDARD_UTTERANCES = {
    # Wake/Response sounds
    "yes.wav": "Yes?",
    "you_called.wav": "You called?",
    "listening.wav": "Listening.",
    "hello.wav": "Hello.",
    "hi_how_can_i_help.wav": "Hi there, how can I help?",
    
    # Thinking/filler sounds
    "ummm.wav": "Ummmm",
    "ehhh.wav": "Ehhhh",
    "uhhhh.wav": "Uhhhh",
    "hmmm.wav": "Hmmm",
    
    # Status responses
    "ready.wav": "{assistant_name} ready.",
    "something_went_wrong.wav": "Something went wrong.",
    "the_current_time_is.wav": "The current time is",
    "goodbye.wav": "Goodbye."
}

def generate_assistant_sounds(assistant_name, utterance_phrase, output_dir):
    """
    Generate all standard assistant sounds using Piper TTS
    
    Args:
        assistant_name: Name of the assistant (folder will be created if it doesn't exist)
        output_dir: Base directory for sounds (usually 'sounds')
    """
    # Ensure the assistant directory exists
    assistant_dir = Path(output_dir) / assistant_name.lower()
    assistant_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate each utterance
    total = len(STANDARD_UTTERANCES)
    for i, (filename, text) in enumerate(STANDARD_UTTERANCES.items(), 1):
        if utterance_phrase and utterance_phrase not in text:
            continue
        output_path = assistant_dir / filename
        
        print(f"Generating [{i}/{total}]: {filename}")
        try:
            # Run piper-tts to generate the WAV file
            subprocess.run(
                ['piper', '--model', f"piper_models/{assistant_name.lower()}.onnx", '--output_file', str(output_path)],
                input=text.format(assistant_name=assistant_name.lower()),
                text=True,
                check=True
            )
            print(f"  Created {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"  Error generating {filename}: {e}")
    
    print(f"\nCompleted! Generated {total} sound files for {assistant_name} in {assistant_dir}")
    print("Use these files with the SoundEffectService in your assistant.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate standard assistant sounds using Piper TTS")
    parser.add_argument("--assistant-name", required=True, help="Name of the assistant (e.g., 'jarvis', 'friday')")
    parser.add_argument("--utterance-phrase", default="", help="a single phrase to generate a sound for")
    parser.add_argument("--output-dir", default="sounds/piper", help="Base output directory")
    
    args = parser.parse_args()
    
    generate_assistant_sounds(
        args.assistant_name,
        args.utterance_phrase,
        args.output_dir
    )