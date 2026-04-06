"""
System prompt construction and character context management.
Builds the 'brain' instructions for the LLM based on character and user profiles.
"""

import json
import os

from engines.utilities import replace_placeholders

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

def build_system_prompt(profile: dict, rel_score: int, rel_label: str, action_req: str, tone_mod: str, mode: str = "rp", system_extra_info: str = None) -> str:
    """
    Constructs the master system prompt for the LLM.
    Combines character backstory, mannerisms, user details, and behavioral rules.

    Args:
        profile (dict): The active companion's profile data.
        rel_score (int): Current relationship score (-100 to 100).
        rel_label (str): Textual label for the relationship (e.g., 'Soulmate').
        action_req (str): Instruction on whether to obey or refuse requests.
        tone_mod (str): Instruction on the tone of the response.
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
    system_content = f"""{base_prompt}

{char_details}
{user_details}

[CONTEXT]
Rel: {rel_label} ({rel_score}/100)
Action: {action_req}
Tone: {tone_mod}
Mode: {mode.upper()}
"""

    # 4. Global Behavioral Rules
    if mode == "casual":
        rule = """
[BEHAVIOR RULES: CASUAL MODE]
1. STAY IN CHARACTER at all times.
2. CONSISE: Keep responses short, direct, and conversational.
3. NO NARRATION: Do NOT use asterisks (*...*) for actions or narration. Use only spoken dialogue.
4. RELATIONSHIP: Your tone MUST reflect your current Relationship Score.
"""
    else:  # Default to RP
        rule = """
[BEHAVIOR RULES: RP MODE]
1. STAY IN CHARACTER at all times.
2. ALWAYS move the story forward naturally.
3. DIALOGUE vs ACTION: Put narration/actions (*...*) on a SEPARATE LINE from spoken dialogue.
   - Good: *She smiles.* \n "Hello there."
4. MANNERISMS: Weave your listed mannerisms into your actions.
5. RELATIONSHIP: Your tone and willingness to help MUST reflect your current Relationship Score.
"""

    if system_extra_info:
        system_content += f"Note: {system_extra_info}\n"

    system_content += f"{rule}"

    ### Final pass to replace any placeholders in the base prompt with actual values from the profile
    system_content = replace_placeholders(system_content, user_name=user_profile.get("name", "User") if user_profile else "User", char_name=profile.get("name", "Assistant"))

    return system_content
