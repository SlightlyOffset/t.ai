import os
import json
import pytest
from engines.config import get_setting, update_setting

def test_interaction_mode_setting():
    # Verify default value
    mode = get_setting("interaction_mode")
    assert mode == "rp"

    # Verify update to casual
    update_setting("interaction_mode", "casual")
    assert get_setting("interaction_mode") == "casual"

    # Reset back to rp for other tests/runs
    update_setting("interaction_mode", "rp")
    assert get_setting("interaction_mode") == "rp"
