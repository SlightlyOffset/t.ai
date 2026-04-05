import asyncio
import os
from engines.tts_module import generate_edge_tts, play_audio

async def test():
    filename = "test_diag.mp3"
    try:
        print("--- Step 1: Generating Audio ---")
        await generate_edge_tts("Diagnostic test.", filename)
        if os.path.exists(filename):
            print(f"SUCCESS: {filename} created. Size: {os.path.getsize(filename)} bytes.")
            print("\n--- Step 2: Playing Audio ---")
            play_audio(filename)
            print("Playback finished.")
        else:
            print("FAILURE: File not created.")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    asyncio.run(test())
