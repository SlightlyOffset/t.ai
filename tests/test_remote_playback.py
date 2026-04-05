
import os
import sys
from engines.tts_module import generate_audio, play_audio
from engines.config import update_setting

def test_remote_xtts_playback():
    # Ensure remote URL is set (use the one from the user's log if possible, but let's just use what's in settings)
    print("Testing Remote XTTS Playback...")
    
    text = "This is a test of the remote voice cloning system. If you can hear this, the playback is working correctly."
    filename = "test_remote.mp3"
    
    # We need a valid reference voice
    ref_voice = "voices/Astgenne.wav"
    if not os.path.exists(ref_voice):
        print(f"Error: {ref_voice} not found. Please ensure it exists.")
        return

    print(f"Generating audio for: '{text}'")
    success = generate_audio(
        text=text, 
        filename=filename, 
        engine="xtts", 
        clone_ref=ref_voice,
        language="en"
    )
    
    if success:
        if os.path.exists(filename):
            print(f"Successfully generated {filename}. Size: {os.path.getsize(filename)} bytes.")
            print("Starting playback...")
            play_audio(filename)
            print("Playback finished.")
        else:
            print(f"Error: generate_audio returned True but {filename} does not exist!")
    else:
        print("Error: generate_audio failed.")

if __name__ == "__main__":
    test_remote_xtts_playback()
