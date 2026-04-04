import os
import sys
import time
from colorama import Fore, init

# Add current directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engines.tts_module import generate_audio, STYLETTS2_AVAILABLE

init(autoreset=True)

def test_styletts2():
    print(Fore.CYAN + "--- StyleTTS 2 Local Verification ---")
    
    if not STYLETTS2_AVAILABLE:
        print(Fore.RED + "[ERROR] styletts2 package not found in environment.")
        return

    # Use existing sample
    ref_voice = "voices/Astgenne/neutral01.wav"
    if not os.path.exists(ref_voice):
        print(Fore.YELLOW + f"[WARNING] Reference voice {ref_voice} not found. Testing default model only.")
        ref_voice = None

    output_file = "test_styletts2_output.wav"
    if os.path.exists(output_file):
        os.remove(output_file)

    print(Fore.YELLOW + "Generating audio... (First run may take a moment to download model)")
    start_time = time.time()
    
    success = generate_audio(
        text="Hello! This is a test of StyleTTS 2 high performance voice cloning.",
        filename=output_file,
        engine="styletts2",
        clone_ref=ref_voice
    )
    
    end_time = time.time()

    if success and os.path.exists(output_file):
        print(Fore.GREEN + f"[SUCCESS] Audio generated in {end_time - start_time:.2f} seconds.")
        print(Fore.GREEN + f"Output saved to: {output_file}")
    else:
        print(Fore.RED + "[FAILURE] Failed to generate audio.")

if __name__ == "__main__":
    test_styletts2()
