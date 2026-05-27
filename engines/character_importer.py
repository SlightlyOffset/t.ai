import json
import os
import base64
import re
import shutil
from PIL import Image
from colorama import Fore

class CharacterImporter:
    """
    Handles importing and converting character profiles from external formats.
    Currently supports SillyTavern Chara Card V2 (PNG and JSON).
    """

    @staticmethod
    def extract_from_png(image_path):
        """Extracts character metadata from a SillyTavern PNG card."""
        try:
            with Image.open(image_path) as img:
                # IMPORTANT: load() ensures all chunks (including those after IDAT) are read
                img.load()

                # Try both 'chara' (V2) and 'ccv3' (V3) in info and text attributes
                raw_data = None
                for key in ["chara", "ccv3"]:
                    raw_data = img.info.get(key)
                    if not raw_data and hasattr(img, "text"):
                        raw_data = img.text.get(key)
                    if raw_data:
                        break

                if not raw_data:
                    # Fallback to V1 Description key
                    description = img.info.get("Description")
                    if description:
                        name = os.path.basename(image_path).split('.')[0]
                        # Apply basic placeholder replacement for V1 fallback
                        description = description.replace("{{char}}", name).replace("{{user}}", "User").replace("{{user_name}}", "User")
                        return {"name": name, "description": description}
                    return None

                # Decode from Base64
                decoded_bytes = base64.b64decode(raw_data)
                decoded_str = decoded_bytes.decode('utf-8')

                # Parse the JSON
                char_json = json.loads(decoded_str)

                # Chara V2/V3 has a 'data' field containing the actual character info
                if "data" in char_json:
                    return char_json["data"]
                return char_json
        except Exception as e:
            print(f"{Fore.RED}[ERROR] Failed to extract from PNG: {e}")
            return None

    @staticmethod
    def convert_to_project_format(st_data, avatar_path=None):
        """Maps SillyTavern data to the local profile format."""
        if not st_data:
            return None

        # Helper to get field with fallback
        def g(field, default=""):
            val = st_data.get(field, default)
            return val if val else default

        char_name = g("name")

        def replace_placeholders(text):
            if not text:
                return ""
            text = text.replace("{{char}}", char_name)
            text = text.replace("<START>", "")
            # Remove any excess newlines or carriage returns
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            return text.strip()

        # Basic mapping
        profile = {
            "name": char_name,
            "avatar_path": avatar_path or "img/No_Image_Error.png",
            "alt_names": "",
            "personality_type": replace_placeholders(g("personality")),
            "backstory": replace_placeholders(g("description")),
            "rp_mannerisms": [],
            "character_info": {
                "gender": "Unknown",
                "age": "Unknown",
                "appearance": "",
                "likes": [],
                "dislikes": [],
                "other": replace_placeholders(g("scenario"))
            },
            "starter_messages": [replace_placeholders(g("first_mes"))] if g("first_mes") else [],
            "system_prompt": f"Character: {char_name}\nPersonality: {replace_placeholders(g('personality'))}\nDescription: {replace_placeholders(g('description'))}\nScenario: {replace_placeholders(g('scenario'))}\n{replace_placeholders(g('system_prompt'))}",
            "preferred_edge_voice": "en-US-AvaMultilingualNeural",
            "tts_engine": "edge-tts",
            "voice_clone_ref": None,
            "tts_language": "en",
            "llm_model": None,
            "relationship_score": 0,
            "colors": {
                "text": "WHITE",
                "label": "NORMAL",
                "name_lbl": "magenta",
                "speech_highlight": "yellow"
            }
        }

        # Attempt to extract mannerisms from message examples
        mes_example = replace_placeholders(g("mes_example"))
        if mes_example:
            # Look for actions/descriptions in asterisks (classic ST style)
            actions = re.findall(r'\*([^*]+)\*', mes_example)
            if actions:
                # Clean up and limit to unique, short mannerisms
                cleaned_actions = []
                for a in actions:
                    a_clean = a.strip()
                    if 5 < len(a_clean) < 60 and a_clean not in cleaned_actions:
                        cleaned_actions.append(a_clean)
                profile["rp_mannerisms"] = cleaned_actions[:5]

        # Handle alternate greetings
        alt_greetings = st_data.get("alternate_greetings", [])
        if alt_greetings:
            profile["starter_messages"].extend([replace_placeholders(ag) for ag in alt_greetings])

        return profile

    @staticmethod
    def save_profile(profile, filename=None):
        """Saves the converted profile to the profiles/ directory."""
        if not profile or not profile.get("name"):
            return False

        from engines.utilities import sanitize_profile_name

        if not filename:
            # Sanitize the name to prevent path traversal
            safe_name = sanitize_profile_name(profile["name"])
            filename = safe_name + ".json"

        # Ensure we only have the basename of the filename
        filename = os.path.basename(filename)

        if not filename.endswith(".json"):
            filename += ".json"

        # Construct target path relative to profiles directory
        profiles_dir = os.path.abspath("profiles")
        target_path = os.path.abspath(os.path.join(profiles_dir, filename))

        # Security check: Ensure the target path is still within the profiles directory
        if not target_path.startswith(profiles_dir):
            print(f"{Fore.RED}[ERROR] Path traversal attempt detected: {target_path}")
            return False

        # Ensure profiles directory exists
        os.makedirs(profiles_dir, exist_ok=True)

        try:
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=4, ensure_ascii=False)
            return target_path
        except Exception as e:
            print(f"{Fore.RED}[ERROR] Failed to save profile: {e}")
            return False

def import_character(source_path):
    """Main entry point for importing a character."""
    data = None
    avatar_path = "img/No_Image_Error.png"

    if source_path.lower().endswith((".png", ".webp")):
        data = CharacterImporter.extract_from_png(source_path)
        if data and "name" in data:
            char_name = data["name"]
            # Create a safe filename for the image
            safe_name = re.sub(r'[^\w\s-]', '', char_name).strip().replace(' ', '_')
            ext = os.path.splitext(source_path)[1]
            dest_image = os.path.join("img", f"{safe_name}{ext}")

            os.makedirs("img", exist_ok=True)
            try:
                shutil.copy2(source_path, dest_image)
                avatar_path = dest_image.replace("\\", "/") # Use forward slashes for consistency
            except Exception as e:
                print(f"{Fore.RED}[ERROR] Failed to copy avatar image: {e}")

    elif source_path.lower().endswith(".json"):
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
                if "data" in raw_json:
                    data = raw_json["data"]
                else:
                    data = raw_json
        except Exception as e:
            print(f"{Fore.RED}[ERROR] Failed to read JSON: {e}")
            return None

    if not data:
        print(f"{Fore.RED}[ERROR] Could not find character data in {source_path}")
        return None

    new_profile = CharacterImporter.convert_to_project_format(data, avatar_path=avatar_path)
    save_path = CharacterImporter.save_profile(new_profile)

    if save_path:
        print(f"{Fore.GREEN}[SUCCESS] Imported {new_profile['name']} to {save_path}")
        if avatar_path != "img/No_Image_Error.png":
             print(f"{Fore.GREEN}[SUCCESS] Saved avatar to {avatar_path}")
        print(f"{Fore.YELLOW}[INFO] Conversion may be imperfect. It is recommended to review the profile and adjust any fields as necessary.")
        return save_path
    return None
