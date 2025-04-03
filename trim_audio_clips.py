import os
import csv
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from datetime import timedelta

def hms_to_seconds(t_str):
    """Converts time string to seconds (float). Supports both MM:SS.ms and HH:MM:SS.ms formats."""
    parts = t_str.split(':')
    
    if len(parts) == 2:  # MM:SS.ms format
        minutes = int(parts[0])
        sec_ms = parts[1].split('.')
        seconds = int(sec_ms[0])
        milliseconds = int(sec_ms[1]) if len(sec_ms) > 1 else 0
        total_seconds = timedelta(minutes=minutes, seconds=seconds, milliseconds=milliseconds).total_seconds()
    else:  # HH:MM:SS.ms format
        hours = int(parts[0])
        minutes = int(parts[1])
        sec_ms = parts[2].split('.')
        seconds = int(sec_ms[0])
        milliseconds = int(sec_ms[1]) if len(sec_ms) > 1 else 0
        total_seconds = timedelta(hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds).total_seconds()
    
    return round(total_seconds)

def hms_to_milliseconds(t_str):
    """Converts time string to milliseconds (int). Supports both MM:SS.ms and HH:MM:SS.ms formats."""
    parts = t_str.split(':')
    
    if len(parts) == 2:  # MM:SS.ms format
        minutes = int(parts[0])
        sec_ms = parts[1].split('.')
        seconds = int(sec_ms[0])
        milliseconds = int(sec_ms[1]) if len(sec_ms) > 1 else 0
        total_ms = minutes * 60000 + seconds * 1000 + milliseconds
    else:  # HH:MM:SS.ms format
        hours = int(parts[0])
        minutes = int(parts[1])
        sec_ms = parts[2].split('.')
        seconds = int(sec_ms[0])
        milliseconds = int(sec_ms[1]) if len(sec_ms) > 1 else 0
        total_ms = hours * 3600000 + minutes * 60000 + seconds * 1000 + milliseconds
    
    return total_ms

def detect_audio_boundaries(audio_segment, start_ms, end_ms, silence_threshold=-50, min_silence_len=100):
    """
    Detect actual audio boundaries within the given time range by finding non-silent regions.
    Treats the provided start_ms and end_ms as rough estimates, and searches for the actual
    speech boundaries near these timestamps.
    
    Parameters:
    - audio_segment: The pydub AudioSegment
    - start_ms, end_ms: The initial time range (rough estimates) to analyze
    - silence_threshold: dBFS value below which is considered silence (default: -50)
    - min_silence_len: minimum length of silence in ms (default: 100)
    
    Returns:
    - Tuple of (refined_start_ms, refined_end_ms)
    """
    # Define a larger analysis window around the rough timestamps
    search_margin = 1500  # 1.5 seconds margin to search for actual speech
    
    # Calculate analysis boundaries
    analysis_start = max(0, start_ms - search_margin)
    analysis_end = min(len(audio_segment), end_ms + search_margin)
    
    # Extract the segment for analysis
    segment_to_analyze = audio_segment[analysis_start:analysis_end]
    
    # Detect non-silent parts
    non_silent_ranges = detect_nonsilent(segment_to_analyze, 
                                         min_silence_len=min_silence_len,
                                         silence_thresh=silence_threshold)
    
    if not non_silent_ranges:  # If no non-silent parts detected
        # Fall back to original rough estimates
        return start_ms, end_ms
    
    # Find the appropriate speech boundary
    # Convert ranges to absolute timestamps
    absolute_ranges = [(analysis_start + start, analysis_start + end) 
                      for start, end in non_silent_ranges]
    
    # For the refined start: find the first non-silent range that starts before or at the original end time
    refined_start = start_ms  # Default fallback
    for speech_start, speech_end in absolute_ranges:
        if speech_end >= start_ms:
            refined_start = speech_start
            break
    
    # For the refined end: find the last non-silent range that ends after or at the original start time
    refined_end = end_ms  # Default fallback
    for speech_start, speech_end in reversed(absolute_ranges):
        if speech_start <= end_ms:
            refined_end = speech_end
            break
    
    return refined_start, refined_end

# --- Configuration ---
audio_file_path = 'bluey-pranks.mp3' # <--- CHANGE THIS TO YOUR AUDIO FILE NAME/PATH
metadata_file_path = 'bluey-pranks.csv'
output_directory = 'bluey_pranks_clips'
output_metadata_path = 'bluey-pranks-metadata.csv'  # New simplified metadata file to be created

# Padding configuration (in milliseconds)
padding_start = 200  # Padding before the detected speech starts
padding_end = 300    # Padding after the detected speech ends

# Silence detection settings (Set to None to disable auto-refinement)
auto_refine_boundaries = True  # Set to False to disable silence detection
silence_threshold = -35  # dBFS threshold (higher = less sensitive, includes more audio)
min_silence_len = 25    # Minimum silence length in ms to consider as a break
# --- End Configuration ---

# Create output directory if it doesn't exist
os.makedirs(output_directory, exist_ok=True)

print(f"Loading audio file: {audio_file_path}...")
try:
    audio = AudioSegment.from_file(audio_file_path)
    print("Audio loaded successfully.")
    audio_duration_ms = len(audio)
    print(f"Audio duration: {audio_duration_ms/1000:.2f} seconds")
except Exception as e:
    print(f"Error loading audio file: {e}")
    print("Please ensure the audio file path is correct and pydub/ffmpeg are installed.")
    exit()

print(f"Processing metadata file: {metadata_file_path}...")
try:
    with open(metadata_file_path, mode='r', encoding='utf-8') as infile, \
         open(output_metadata_path, mode='w', encoding='utf-8', newline='') as outfile:
        reader = csv.reader(infile, delimiter='|')
        writer = csv.writer(outfile, delimiter='|')
        header = next(reader) # Skip header row

        total_clips = 0
        processed_clips = 0

        # Count total clips first for progress indication
        infile.seek(0) # Go back to start
        next(reader) # Skip header again
        total_clips = sum(1 for row in reader)
        infile.seek(0) # Reset again for processing
        next(reader) # Skip header once more
        
        print(f"Found {total_clips} clips to process.")
        print(f"Using padding: {padding_start}ms before, {padding_end}ms after")
        if auto_refine_boundaries:
            print(f"Auto-refinement enabled: silence threshold={silence_threshold}dBFS, min_silence_len={min_silence_len}ms")
        else:
            print("Auto-refinement disabled")
        
        print(f"Creating simplified metadata file: {output_metadata_path}")

        for i, row in enumerate(reader):
            if len(row) != 4:
                print(f"Skipping invalid row {i+2}: {row}")
                continue

            filename_base, start_time_str, end_time_str, transcription = row
            output_wav_path = os.path.join(output_directory, f"{filename_base}.wav")
            
            try:
                start_ms = hms_to_milliseconds(start_time_str.strip())
                end_ms = hms_to_milliseconds(end_time_str.strip())

                if start_ms >= end_ms:
                    print(f"Skipping clip {filename_base}: Start time ({start_time_str}) is not before end time ({end_time_str}).")
                    continue
                
                # Apply auto-refinement if enabled
                if auto_refine_boundaries:
                    original_start = start_ms
                    original_end = end_ms
                    start_ms, end_ms = detect_audio_boundaries(
                        audio, start_ms, end_ms, 
                        silence_threshold=silence_threshold,
                        min_silence_len=min_silence_len
                    )
                    if start_ms != original_start or end_ms != original_end:
                        print(f"  Refined boundaries: {original_start}ms→{start_ms}ms, {original_end}ms→{end_ms}ms")
                
                # Apply padding
                final_start_ms = max(0, start_ms - padding_start)
                final_end_ms = min(audio_duration_ms, end_ms + padding_end)
                
                if final_end_ms > audio_duration_ms:
                    print(f"Warning for clip {filename_base}: End time with padding ({final_end_ms}ms) exceeds audio duration ({audio_duration_ms}ms). Clipping to end.")
                    final_end_ms = audio_duration_ms

                print(f"Processing {filename_base}: {start_time_str} → {end_time_str} (with padding: {final_start_ms}ms → {final_end_ms}ms)")

                # Extract the segment with precise millisecond control
                audio_segment = audio[final_start_ms:final_end_ms]

                # Export as WAV with high quality settings
                audio_segment.export(
                    output_wav_path,
                    format="wav",
                    parameters=["-ac", "1", "-ar", "44100"]  # Mono, 44.1kHz sample rate
                )
                
                # Write to the simplified metadata file (filename without extension | transcription)
                writer.writerow([filename_base, transcription])
                
                processed_clips += 1
                print(f"  → Saved {output_wav_path} ({processed_clips}/{total_clips})")

            except ValueError as ve:
                print(f"Skipping clip {filename_base}: Error parsing time '{start_time_str}' or '{end_time_str}'. Details: {ve}")
            except Exception as e:
                print(f"Skipping clip {filename_base}: Error processing. Details: {e}")

except FileNotFoundError:
    print(f"Error: Metadata file not found at '{metadata_file_path}'")
    exit()
except Exception as e:
    print(f"An unexpected error occurred while reading the CSV: {e}")
    exit()

print("\nProcessing complete.")
print(f"Successfully created {processed_clips} WAV files in '{output_directory}'.")
print(f"Created simplified metadata file at '{output_metadata_path}' with {processed_clips} entries.")