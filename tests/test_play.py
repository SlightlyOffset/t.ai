import os
import time
import asyncio
from engines.tts_module import generate_edge_tts

async def test_alt():
    filename = "test_alt.mp3"
    await generate_edge_tts("Testing alternative playback.", filename)
    print(f"Generated {filename}")
    
    # Try startfile (Windows only)
    print("Trying os.startfile...")
    os.startfile(filename)
    time.sleep(3)
    
    if os.path.exists(filename):
        os.remove(filename)

if __name__ == "__main__":
    asyncio.run(test_alt())
