#!/usr/bin/env python3
"""
Test script for the manifest generator
This script creates a simple test assistant and generates its manifest and icons
"""
import os
import json
import subprocess
from pathlib import Path

# Create test directories
test_dir = Path("manifest_test")
test_dir.mkdir(exist_ok=True)
test_static = test_dir / "static"
test_static.mkdir(exist_ok=True)
test_images = test_static / "images"
test_images.mkdir(exist_ok=True)

# Create a test assistants.json file
test_assistants = {
    "test_assistant": {
        "name": "TestBot",
        "wake_word": "hey test",
        "gender": "neutral",
        "accent": "us",
        "page_title": "T.E.S.T. Bot",
        "acronym": "Totally Excellent Smart Technology",
        "theme_color": "#9b59b6",  # Purple color
        "descr": "This is a test assistant for demonstration purposes only."
    }
}

# Write test assistants.json
with open(test_dir / "assistants.json", 'w') as f:
    json.dump(test_assistants, f, indent=4)

print("Created test assistants.json file")

# Run the generator script
print("\nRunning manifest generator...")
cmd = ["python", "generate_manifest.py", 
       "--assistants-json", str(test_dir / "assistants.json"),
       "--output-dir", str(test_static),
       "--images-dir", str(test_images)]

try:
    subprocess.run(cmd, check=True)
    
    # Verify files were created
    print("\nVerifying generated files...")
    expected_files = [
        test_static / "testbot-manifest.json",
        test_images / "testbot-android-chrome-192x192.png",
        test_images / "testbot-android-chrome-512x512.png",
        test_images / "testbot-apple-touch-icon.png",
        test_images / "testbot-favicon-16x16.png",
        test_images / "testbot-favicon-32x32.png",
        test_images / "testbot-favicon-48x48.png",
        test_images / "testbot-favicon.ico"
    ]
    
    all_exist = True
    for file_path in expected_files:
        if file_path.exists():
            print(f"✓ {file_path.relative_to(test_dir)}")
        else:
            print(f"✗ {file_path.relative_to(test_dir)} (missing)")
            all_exist = False
    
    if all_exist:
        print("\nSuccess! All files were generated correctly.")
        print(f"\nYou can find the generated files in the '{test_dir}' directory.")
    else:
        print("\nSome files are missing. Please check the output above.")
    
except subprocess.CalledProcessError as e:
    print(f"Error running manifest generator: {e}")
    
print("\nTest completed.") 