import pytest
from engines.app_commands import app_commands
from engines.config import get_setting, update_setting

def test_toggle_mode_command(capsys):
    # Ensure starting state
    update_setting("interaction_mode", "rp")
    
    # Toggle to casual
    assert app_commands("//mode") is True
    assert get_setting("interaction_mode") == "casual"
    captured = capsys.readouterr()
    assert "Interaction mode set to CASUAL" in captured.out

    # Toggle back to rp
    assert app_commands("//mode") is True
    assert get_setting("interaction_mode") == "rp"
    captured = capsys.readouterr()
    assert "Interaction mode set to RP" in captured.out
