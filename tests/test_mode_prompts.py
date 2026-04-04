import pytest
from engines.prompts import build_system_prompt

def test_prompt_modes():
    profile = {
        "name": "TestChar",
        "system_prompt": "You are a test character.",
        "backstory": "Test backstory.",
        "rp_mannerisms": ["test mannerism"],
        "character_info": {"likes": ["testing"], "dislikes": ["bugs"]}
    }
    
    # Test RP Mode output
    rp_prompt = build_system_prompt(profile, 0, "Neutral", "Respond normally.", "Balanced", mode="rp")
    assert "[BEHAVIOR RULES: RP MODE]" in rp_prompt
    assert "Put narration/actions (*...*) on a SEPARATE LINE" in rp_prompt
    assert "Mode: RP" in rp_prompt

    # Test Casual Mode output
    casual_prompt = build_system_prompt(profile, 0, "Neutral", "Respond normally.", "Balanced", mode="casual")
    assert "[BEHAVIOR RULES: CASUAL MODE]" in casual_prompt
    assert "NO NARRATION: Do NOT use asterisks (*...*)" in casual_prompt
    assert "Mode: CASUAL" in casual_prompt
