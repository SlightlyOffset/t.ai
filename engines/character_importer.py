import json
import os
import base64
import re
import shutil
from PIL import Image
from colorama import Fore

def _heal_and_load_json(text):
    """Attempts to parse JSON, healing unescaped quotes if needed."""
    try:
        return json.loads(text)
    except Exception:
        try:
            key_pattern = r'[a-zA-Z0-9_-]+'
            pattern = re.compile(
                r'("(' + key_pattern + r')"\s*:\s*")(.*?)("(?=\s*(?:,\s*"' + key_pattern + r'"\s*:|\s*\})))',
                re.DOTALL
            )
            def replacer(match):
                prefix = match.group(1)
                val = match.group(3)
                suffix = match.group(4)
                escaped_val = re.sub(r'(?<!\\)"', r'\"', val)
                return prefix + escaped_val + suffix
            healed = pattern.sub(replacer, text)
            return json.loads(healed)
        except Exception:
            raise

class CharacterImporter:
    """
    Handles importing and converting character profiles from external formats.
    Currently supports SillyTavern Chara Card V2 (PNG and JSON).
    """

    @staticmethod
    def get_default_refine_model():
        """Gets the default LLM model to use for character refinement."""
        from engines.config import get_setting
        try:
            config_path = os.path.join("plugins", "mcp_st_importer", "plugin.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    refine_model = cfg.get("refine_model")
                    if refine_model:
                        return refine_model
        except Exception:
            pass
        return get_setting("default_llm_model", "llama3.2")

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

        def listify(val):
            if isinstance(val, list):
                return [str(x).strip() for x in val if x]
            if isinstance(val, str):
                if not val.strip():
                    return []
                import re
                return [x.strip() for x in re.split(r'[,;\n]', val) if x.strip()]
            return []

        # Conditional extraction of other fields
        preferred_edge_voice = st_data.get("preferred_edge_voice") or st_data.get("preferred_tts_voice") or "en-US-AvaMultilingualNeural"
        tts_engine = st_data.get("tts_engine") or "edge-tts"
        voice_clone_ref = st_data.get("voice_clone_ref") or ""
        tts_language = st_data.get("tts_language") or "en"
        llm_model = st_data.get("llm_model") or ""
        
        try:
            relationship_score = int(st_data.get("relationship_score", 0))
        except (ValueError, TypeError):
            relationship_score = 0
            
        # Colors conditional extraction
        default_colors = {
            "text": "WHITE",
            "label": "NORMAL",
            "name_lbl": "magenta",
            "speech_highlight": "yellow"
        }
        colors = st_data.get("colors")
        if not colors or not isinstance(colors, dict):
            colors = default_colors
        else:
            # Merge with default to ensure no missing keys
            colors = {**default_colors, **colors}
 
        # Basic mapping with fallback conditional extraction
        profile = {
            "name": char_name,
            "avatar_path": avatar_path or st_data.get("avatar_path") or "img/No_Image_Error.png",
            "alt_names": st_data.get("alt_names") or "",
            "personality_type": replace_placeholders(g("personality")),
            "backstory": replace_placeholders(g("description")),
            "rp_mannerisms": [],
            "character_info": {
                "gender": (st_data.get("character_info", {}).get("gender") if isinstance(st_data.get("character_info"), dict) else st_data.get("gender")) or "Unknown",
                "age": (st_data.get("character_info", {}).get("age") if isinstance(st_data.get("character_info"), dict) else st_data.get("age")) or "Unknown",
                "appearance": (st_data.get("character_info", {}).get("appearance") if isinstance(st_data.get("character_info"), dict) else st_data.get("appearance")) or "",
                "likes": listify(st_data.get("character_info", {}).get("likes") if isinstance(st_data.get("character_info"), dict) else st_data.get("likes")),
                "dislikes": listify(st_data.get("character_info", {}).get("dislikes") if isinstance(st_data.get("character_info"), dict) else st_data.get("dislikes")),
                "other": replace_placeholders(g("scenario"))
            },
            "starter_messages": st_data.get("starter_messages") if isinstance(st_data.get("starter_messages"), list) else ([replace_placeholders(g("first_mes"))] if g("first_mes") else []),
            "system_prompt": st_data.get("system_prompt") or (
                f"You are roleplaying as {char_name}.\n\n"
                f"[Personality]\n{replace_placeholders(g('personality'))}\n\n"
                f"[Backstory]\n{replace_placeholders(g('description'))}\n\n"
                f"[Scenario]\n{replace_placeholders(g('scenario'))}"
            ),
            "preferred_edge_voice": preferred_edge_voice,
            "tts_engine": tts_engine,
            "voice_clone_ref": voice_clone_ref,
            "tts_language": tts_language,
            "llm_model": llm_model,
            "lorebook_path": st_data.get("lorebook_path") or "",
            "relationship_score": relationship_score,
            "colors": colors
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
    def refine_character_profile(profile, raw_st_data=None, model=None):
        """
        Uses a local LLM to refine and clean character profile metadata fields.
        Returns the updated profile (modifying fields like alt_names, character_info, backstory, rp_mannerisms).
        """
        from engines.config import get_setting
        from engines.responses import _ollama_chat_compat

        if not profile:
            return profile

        refine_model = model or CharacterImporter.get_default_refine_model()
        char_name = profile.get("name", "Unknown")

        # 1. Gather all raw context from raw_st_data or the profile
        raw_personality = ""
        raw_description = ""
        raw_scenario = ""
        raw_mes_example = ""

        if raw_st_data:
            raw_personality = raw_st_data.get("personality", "")
            raw_description = raw_st_data.get("description", "")
            raw_scenario = raw_st_data.get("scenario", "")
            raw_mes_example = raw_st_data.get("mes_example", "")

        # Fallback to existing profile fields if raw_st_data is missing
        if not raw_personality:
            raw_personality = profile.get("personality_type", "")
        if not raw_description:
            raw_description = profile.get("backstory", "")
        if not raw_scenario:
            raw_scenario = profile.get("character_info", {}).get("other", "")

        # 2. Formulate prompt
        system_prompt = (
            "You are an expert character profile extraction and cleaning assistant.\n"
            "Analyze the provided raw character information and extract structured details strictly based on the text.\n"
            "Respond ONLY with a valid JSON object matching the following schema. "
            "Do not include any conversational intro/outro text, explanations, or code blocks.\n\n"
            "{\n"
            '  "alt_names": "Comma-separated string of nicknames, aliases or alternative names, or empty string",\n'
            '  "gender": "Character gender (e.g. Male, Female, Non-binary, Unknown)",\n'
            '  "age": "Character age (e.g. 24, Unknown)",\n'
            '  "appearance": "Short description of appearance, height, hair, clothing, eyes",\n'
            '  "likes": ["list of strings containing likes/hobbies, or empty list"],\n'
            '  "dislikes": ["list of strings containing dislikes/aversions, or empty list"],\n'
            '  "rp_mannerisms": ["List of 3-5 specific conversational traits, e.g. \'frequently stutters when nervous\', \'speaks in a polite, formal tone\'"],\n'
            '  "personality_type": "Concise 1-3 sentence summary of personality",\n'
            '  "backstory": "Clean, narrative biography summary of history and origin",\n'
            '  "other": "Refined description of the roleplay scenario or other setting details",\n'
            '  "system_prompt": "A highly immersive, refined system prompt for the roleplay. Synthesize the raw backstory, personality, scenario, and examples into active, direct instructions for the AI on how to act, talk, and behave as this character. Write in the second person (e.g. \'You are [Name], a...\'). Do NOT copy the raw backstory or scenario verbatim. Outline their tone, speech pattern, mannerisms, and formatting instructions (e.g. asterisks for actions) in a clean, structured, and actionable format. Limit to 3-5 concise, high-impact paragraphs."\n'
            "}"
        )

        user_content = (
            f"Character Name: {char_name}\n"
            f"Raw Personality:\n{raw_personality}\n\n"
            f"Raw Description/Backstory:\n{raw_description}\n\n"
            f"Raw Scenario/Other Details:\n{raw_scenario}\n\n"
            f"Raw Dialogue Examples:\n{raw_mes_example}\n\n"
            "Strict Instructions:\n"
            "1. Extract only facts directly mentioned or clearly implied for the attributes (gender, age, appearance, likes, dislikes).\n"
            "2. If age or gender are not mentioned or cannot be inferred, use 'Unknown'.\n"
            "3. Do not invent backstory details. Keep it grounded.\n"
            "4. For 'system_prompt', synthesize and write a highly refined, active roleplay instruction set in the second person ('You are...'). Do NOT copy the raw fields verbatim; construct a clean, cohesive, and immersive directive detailing the character's persona, attitude, tone, speech pattern, and mannerisms.\n"
            "5. Translate any weird formatting syntax (such as W++ format, e.g. [Attribute(\"value\")] or [Attribute + value]) into clean, natural human prose for all textual fields.\n"
            "6. Return ONLY valid JSON."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        # Define the structured tool calling schema
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "save_refined_profile",
                    "description": "Submits the fully structured, cleaned, and refined character profile details.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "alt_names": {
                                "type": "string",
                                "description": "Comma-separated string of nicknames, aliases or alternative names, or empty string"
                            },
                            "gender": {
                                "type": "string",
                                "description": "Character gender (e.g. Male, Female, Non-binary, Unknown)"
                            },
                            "age": {
                                "type": "string",
                                "description": "Character age (e.g. 24, Unknown)"
                            },
                            "appearance": {
                                "type": "string",
                                "description": "Short description of appearance, height, hair, clothing, eyes"
                            },
                            "likes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of strings containing likes/hobbies, or empty list"
                            },
                            "dislikes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of strings containing dislikes/aversions, or empty list"
                            },
                            "rp_mannerisms": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of 3-5 specific conversational traits, e.g. 'frequently stutters when nervous', 'speaks in a polite, formal tone'"
                            },
                            "personality_type": {
                                "type": "string",
                                "description": "Concise 1-3 sentence summary of personality"
                            },
                            "backstory": {
                                "type": "string",
                                "description": "Clean, narrative biography summary of history and origin"
                            },
                            "other": {
                                "type": "string",
                                "description": "Refined description of the roleplay scenario or other setting details"
                            },
                            "system_prompt": {
                                "type": "string",
                                "description": (
                                    "A highly immersive, refined system prompt for the roleplay. "
                                    "Synthesize the raw backstory, personality, scenario, and examples into active, "
                                    "direct instructions for the AI on how to act, talk, and behave as this character. "
                                    "Write in the second person (e.g. 'You are [Name], a...'). Do NOT copy the raw "
                                    "backstory or scenario verbatim. Outline their tone, speech pattern, mannerisms, "
                                    "and formatting instructions (e.g. asterisks for actions) in a clean, structured, "
                                    "and actionable format. Limit to 3-5 concise, high-impact paragraphs."
                                )
                            }
                        },
                        "required": [
                            "alt_names", "gender", "age", "appearance", "likes", "dislikes", 
                            "rp_mannerisms", "personality_type", "backstory", "other", "system_prompt"
                        ]
                    }
                }
            }
        ]

        try:
            # Call compat function with tools and JSON formatting format='json'
            result = _ollama_chat_compat(
                model=refine_model,
                messages=messages,
                stream=False,
                format="json",
                think=False,
                options={"temperature": 0.1},
                tools=tools
            )

            refined_data = None
            tool_calls = result.get("message", {}).get("tool_calls")
            
            if tool_calls and len(tool_calls) > 0:
                tool_call = tool_calls[0]
                function_data = tool_call.get("function", {})
                func_args_str = function_data.get("arguments", "{}")
                try:
                    if isinstance(func_args_str, dict):
                        refined_data = func_args_str
                    else:
                        refined_data = _heal_and_load_json(func_args_str)
                except Exception as e:
                    print(f"{Fore.YELLOW}[WARNING] Failed to parse tool call arguments: {e}")

            # Fallback to text output parsing if tool calling did not produce structured arguments
            if not refined_data:
                response_content = result.get("message", {}).get("content", "").strip()

                # Check if the response content is a JSON-formatted pseudo-tool call
                # e.g., {"name": "save_refined_profile", "parameters": {...}}
                if response_content.startswith("{") and '"parameters"' in response_content:
                    # Attempt to heal missing closing braces (very common on local LLMs)
                    for i in range(5):
                        try:
                            candidate = response_content + ("}" * i)
                            pseudo_call = _heal_and_load_json(candidate)
                            if isinstance(pseudo_call, dict) and "parameters" in pseudo_call:
                                refined_data = pseudo_call["parameters"]
                                break
                        except Exception:
                            pass

                if not refined_data:
                    # Refusal detection: check for common safety guidelines / refusal templates
                    refusal_triggers = [
                        "i cannot fulfill", "against safety guidelines", "i am unable to",
                        "cannot generate content", "against policy", "cannot assist with this"
                    ]
                    if any(trigger in response_content.lower() for trigger in refusal_triggers):
                        print(f"{Fore.YELLOW}[WARNING] Local model refused to process character card due to safety constraints. Falling back to rule-based import.")
                        return profile

                    # Parse JSON with healing
                    for i in range(5):
                        try:
                            candidate = response_content + ("}" * i)
                            refined_data = _heal_and_load_json(candidate)
                            if isinstance(refined_data, dict):
                                break
                        except Exception:
                            pass
                            
                    if not refined_data:
                        # Attempt regex-based cleanup of markdown code block
                        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_content, re.DOTALL | re.IGNORECASE)
                        if match:
                            for i in range(5):
                                try:
                                    candidate = match.group(1) + ("}" * i)
                                    refined_data = _heal_and_load_json(candidate)
                                    if isinstance(refined_data, dict):
                                        break
                                except Exception:
                                    pass
                        
                        # Fallback to finding first/last brackets
                        if not refined_data:
                            start = response_content.find('{')
                            end = response_content.rfind('}')
                            if start != -1 and end != -1 and end > start:
                                for i in range(5):
                                    try:
                                        candidate = response_content[start:end+1] + ("}" * i)
                                        refined_data = _heal_and_load_json(candidate)
                                        if isinstance(refined_data, dict):
                                            break
                                    except Exception:
                                        pass

            if not refined_data:
                if get_setting("debug_mode", False):
                    print(f"{Fore.MAGENTA}[DEBUG] Raw model response: {result}{Fore.RESET}")
                print(f"{Fore.YELLOW}[WARNING] Failed to parse AI refinement (both tool calling and JSON parsing failed). Falling back to rule-based values.")
                return profile

            # Clean up any fields that were double-serialized as JSON strings (common on smaller models)
            for list_field in ["likes", "dislikes", "rp_mannerisms"]:
                val = refined_data.get(list_field)
                if isinstance(val, str) and val.strip().startswith("["):
                    try:
                        refined_data[list_field] = json.loads(val)
                    except Exception:
                        pass

            # Merge refined fields into the profile
            if "alt_names" in refined_data and isinstance(refined_data["alt_names"], str):
                profile["alt_names"] = refined_data["alt_names"].strip()
            
            if "personality_type" in refined_data and isinstance(refined_data["personality_type"], str):
                profile["personality_type"] = refined_data["personality_type"].strip()
                
            if "backstory" in refined_data and isinstance(refined_data["backstory"], str):
                profile["backstory"] = refined_data["backstory"].strip()
                
            if "system_prompt" in refined_data and isinstance(refined_data["system_prompt"], str):
                profile["system_prompt"] = refined_data["system_prompt"].strip()

            if "rp_mannerisms" in refined_data and isinstance(refined_data["rp_mannerisms"], list):
                cleaned_mannerisms = [m.strip() for m in refined_data["rp_mannerisms"] if isinstance(m, str) and m.strip()]
                if cleaned_mannerisms:
                    profile["rp_mannerisms"] = cleaned_mannerisms

            # Update character_info dict safely
            if "character_info" not in profile:
                profile["character_info"] = {}
                
            info = profile["character_info"]
            
            if "gender" in refined_data and isinstance(refined_data["gender"], str):
                info["gender"] = refined_data["gender"].strip()
                
            if "age" in refined_data and isinstance(refined_data["age"], str):
                info["age"] = refined_data["age"].strip()
                
            if "appearance" in refined_data and isinstance(refined_data["appearance"], str):
                info["appearance"] = refined_data["appearance"].strip()
                
            if "likes" in refined_data and isinstance(refined_data["likes"], list):
                info["likes"] = [x.strip() for x in refined_data["likes"] if isinstance(x, str) and x.strip()]
                
            if "dislikes" in refined_data and isinstance(refined_data["dislikes"], list):
                info["dislikes"] = [x.strip() for x in refined_data["dislikes"] if isinstance(x, str) and x.strip()]

            other_val = refined_data.get("other") or refined_data.get("other_details")
            if isinstance(other_val, str):
                info["other"] = other_val.strip()

            return profile

        except Exception as e:
            print(f"{Fore.YELLOW}[WARNING] AI refinement failed: {e}. Falling back to rule-based values.")
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
        if not os.path.normcase(target_path).startswith(os.path.normcase(profiles_dir)):
            print(f"{Fore.RED}[ERROR] Path traversal attempt detected.")
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

def import_character(source_path, refine=False, model=None):
    """Main entry point for importing a character with optional AI refinement."""
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
    
    # 1. Save the basic rule-based profile first to ensure critical fields are saved
    save_path = CharacterImporter.save_profile(new_profile)

    if save_path:
        print(f"{Fore.GREEN}[SUCCESS] Character profile imported successfully.")
        if avatar_path != "img/No_Image_Error.png":
             print(f"{Fore.GREEN}[SUCCESS] Saved avatar to {avatar_path}")
             
        # 2. Run AI refinement on top of the saved profile if requested
        if refine:
            refine_model = model or CharacterImporter.get_default_refine_model()
            print(Fore.CYAN + f"[SYSTEM] Running AI profile refinement using local model '{refine_model}'...")
            
            try:
                with open(save_path, "r", encoding="utf-8") as f:
                    saved_profile = json.load(f)
                
                refined_profile = CharacterImporter.refine_character_profile(saved_profile, raw_st_data=data, model=refine_model)
                
                # Overwrite the saved profile with refined contents
                CharacterImporter.save_profile(refined_profile, filename=os.path.basename(save_path))
                print(f"{Fore.GREEN}[SUCCESS] AI refinement complete. Refined fields merged successfully.")
            except Exception as e:
                print(f"{Fore.YELLOW}[WARNING] AI refinement failed: {e}. Keeping the baseline rule-based profile.")
        else:
            print(f"{Fore.YELLOW}[INFO] Conversion may be imperfect. It is recommended to run AI refinement or review the profile.")
            
        return save_path
    return None
