import pytest
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@pytest.fixture(autouse=True)
def cleanup_background_threads():
    yield
    try:
        from engines.responses import active_post_process_threads
        for t in list(active_post_process_threads):
            if t.is_alive():
                t.join(timeout=5.0)  # Allow up to 5 seconds for cleanup
        active_post_process_threads.clear()
    except Exception:
        pass
