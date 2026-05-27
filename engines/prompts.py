"""
System prompt construction and character context management.
Builds the 'brain' instructions for the LLM based on character and user profiles.
"""

import json
import os

from engines.utilities import replace_placeholders

RP_RULES_PATH = "response_rule/rp_rule.md"
CASUAL_RULES_PATH = "response_rule/casual_rule.md"
RELATIONSHIP_INTENSITY_PATH = "response_rule/relationship_intensity.json"

def get_relationship_rule(rel_score: int) -> dict:
    """
    Loads the relationship_intensity.json and returns the correct rule object
    based on the current relationship score.
    """
    if not os.path.exists(RELATIONSHIP_INTENSITY_PATH):
        return {}
    
    try:
        with open(RELATIONSHIP_INTENSITY_PATH, "r", encoding="UTF-8") as f:
            intensity_rules = json.load(f)
            
        # Sort by min_score descending to find the highest bracket the score falls into
        sorted_rules = sorted(intensity_rules.values(), key=lambda x: x["min_score"], reverse=True)
        
        for rule in sorted_rules:
            if rel_score >= rule["min_score"]:
                return rule
                
    except Exception as e:
        print(f"Error loading mood intensity: {e}")
        
    return {}

def load_user_profile():
    """
    Loads the currently selected user profile from the user_profiles directory.

    Returns:
        dict: The user profile data, or None if loading fails.
    """
    from engines.config import get_setting
    user_filename = get_setting("current_user_profile", "Manganese.json")
    user_path = os.path.join("user_profiles", user_filename)

    if os.path.exists(user_path):
        try:
            with open(user_path, "r", encoding="UTF-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def build_system_prompt(profile: dict, rel_score: int, mode: str = "rp", system_extra_info: str = None) -> str:
    """
    Constructs the master system prompt for the LLM.
    Combines character backstory, mannerisms, user details, and behavioral rules.

    Args:
        profile (dict): The active companion's profile data.
        rel_score (int): Current relationship score (-100 to 100).
        mode (str): Interaction mode ('rp' or 'casual').
        system_extra_info (str): Temporary context/notes for this specific turn.

    Returns:
        str: The full system instruction string.
    """
    base_prompt = profile.get("system_prompt", "")

    # 1. Companion Character Details
    backstory = profile.get("backstory", "Unknown.")
    mannerisms = ", ".join(profile.get("rp_mannerisms", []))
    info = profile.get("character_info", {})

    char_details = f"""
[CHARACTER PROFILE]
Name: {profile.get('name', 'Unknown')}
Alternate Names: {profile.get('alt_names', 'None')}
Personality Type: {profile.get('personality_type', 'Unknown')}
Backstory: {backstory}
Age: {info.get('age', 'Unknown')}
Appearance: {info.get('appearance', 'Unknown')}
Likes: {', '.join(info.get('likes', []))}
Dislikes: {', '.join(info.get('dislikes', []))}
Mannerisms: {mannerisms}
"""

    # 2. User Profile Details (Who the AI thinks it's talking to)
    user_profile = load_user_profile()
    user_details = ""
    if user_profile:
        u_info = user_profile.get("character_info", {})
        user_details = f"""
[USER PROFILE (WHO YOU ARE TALKING TO)]
Name: {user_profile.get('name', 'User')}
Personality: {user_profile.get('personality_type', 'Unknown')}
Appearance: {u_info.get('appearance', 'Unknown')}
Pet: {u_info.get('pet', 'None')}
Likes: {', '.join(u_info.get('likes', []))}
Mannerisms to watch for: {', '.join(user_profile.get('rp_mannerisms', []))}
"""

    # 3. Dynamic Context (Relationship and Tone)
    rel_rule = get_relationship_rule(rel_score)
    rel_label = rel_rule.get("label", "Neutral")
    rel_instruction = rel_rule.get("instruction", "") if mode == "rp" else ""
    
    system_content = f"""{base_prompt}

{char_details}
{user_details}

[CONTEXT]
Rel: {rel_label} ({rel_score}/100)
Mode: {mode.upper()}
{rel_instruction}
"""

    # 4. Global Behavioral Rules
    rule_path = RP_RULES_PATH if mode == "rp" else CASUAL_RULES_PATH
    try:
        with open(rule_path, "r", encoding="UTF-8") as f:
            rule = f.read()
    except FileNotFoundError:
        rule = "No response rules."

    if system_extra_info:
        system_content += f"Note: {system_extra_info}\n"

    system_content += f"{rule}"

    ### Final pass to replace any placeholders in the base prompt with actual values from the profile
    system_content = replace_placeholders(system_content, user_name=user_profile.get("name", "User") if user_profile else "User", char_name=profile.get("name", "Assistant"))

    return system_content
