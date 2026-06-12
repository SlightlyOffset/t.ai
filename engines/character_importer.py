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
            "raw_personality": replace_placeholders(g("personality")),
            "raw_description": replace_placeholders(g("description")),
            "mes_example": replace_placeholders(g("mes_example")),
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
            "system_prompt": st_data.get("system_prompt") or f"Character: {char_name}\nPersonality: {replace_placeholders(g('personality'))}\nDescription: {replace_placeholders(g('description'))}\nScenario: {replace_placeholders(g('scenario'))}",
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
    def run_critic_pass(profile, raw_personality, raw_description, raw_scenario, raw_mes_example, model=None):
        """
        Uses a local LLM to critique a refined character profile against raw sources.
        Returns a dictionary with scores and feedback.
        """
        from engines.config import get_setting
        from engines.responses import _ollama_chat_compat

        critic_model = model or get_setting("local_utility_model", "llama3.2")
        char_name = profile.get("name", "Unknown")

        critic_system_prompt = (
            "You are an expert critic and evaluator for AI character roleplay profiles.\n"
            "Your job is to compare a refined character profile against its raw source details and raw dialogue examples.\n"
            "You must rate the quality of the refined profile based on the following criteria (score 1 to 10):\n"
            "1. persona_preservation_score: Does the profile capture the unique voice, accent, vocabulary, slang, and emotional/psychological depth of the original character? (Or did it sanitize/homogenize it?)\n"
            "2. speech_style_alignment_score: Does the profile capture all dialogue formatting, punctuation, capitalization quirks (e.g. all lowercase, stuttering, asterisks for actions) from the dialogue examples?\n"
            "3. accuracy_score: Does it accurately represent facts without inventing/hallucinating unmentioned backstory details?\n\n"
            "CONCISENESS & SYNTHESIS GUIDELINE: Refinement is meant to clean up, summarize, and format the raw details. "
            "Do NOT penalize the proposed profile for being shorter or more concise than the raw data, as long as it preserves the core identity, mannerisms, and key facts. "
            "In fact, you MUST penalize profiles that copy-paste the raw data verbatim into the fields (especially the 'system_prompt' field, which should be a concise instruction prompt in the second person, not a raw dump of description/backstory). "
            "A good refinement is synthesized, clear, and well-structured. A profile that is just a copy-paste of the raw text should receive a very low preservation/alignment score (e.g. 5.0 or lower).\n\n"
            "Respond ONLY with a valid JSON object matching the following schema. "
            "Do not include any conversational intro/outro text, explanations, or code blocks.\n\n"
            "{\n"
            '  "persona_preservation_score": 8.5,\n'
            '  "speech_style_alignment_score": 9.0,\n'
            '  "accuracy_score": 9.5,\n'
            '  "average_score": 9.0,\n'
            '  "feedback": "Explain what is missing or what was sanitized, and provide specific instructions on how to improve the profile."\n'
            "}"
        )

        proposed_profile = {
            "personality_type": profile.get("personality_type", ""),
            "backstory": profile.get("backstory", ""),
            "rp_mannerisms": profile.get("rp_mannerisms", []),
            "system_prompt": profile.get("system_prompt", ""),
            "character_info": profile.get("character_info", {})
        }

        critic_user_content = (
            f"Character Name: {char_name}\n"
            f"--- RAW SOURCE DATA ---\n"
            f"Raw Personality:\n{raw_personality}\n\n"
            f"Raw Description/Backstory:\n{raw_description}\n\n"
            f"Raw Scenario/Other Details:\n{raw_scenario}\n\n"
            f"Raw Dialogue Examples:\n{raw_mes_example}\n\n"
            f"--- PROPOSED REFINED PROFILE ---\n"
            f"{json.dumps(proposed_profile, indent=2)}\n\n"
            "Instructions:\n"
            "Compare the proposed refined profile against the raw source data and rate the quality of the refined profile based on the following criteria (score 1 to 10):\n"
            "1. persona_preservation_score: Does the profile capture the unique voice, accent, vocabulary, slang, and emotional/psychological depth of the original character? (Or did it sanitize/homogenize it?)\n"
            "2. speech_style_alignment_score: Does the profile capture all dialogue formatting, punctuation, capitalization quirks (e.g. all lowercase, stuttering, asterisks for actions) from the dialogue examples?\n"
            "3. accuracy_score: Does it accurately represent facts without inventing/hallucinating unmentioned backstory details?\n\n"
            "CONCISENESS & SYNTHESIS GUIDELINE:\n"
            "- Do NOT penalize the proposed profile for being shorter or more concise than the raw data, as long as it preserves the core identity, mannerisms, and key facts.\n"
            "- You MUST penalize profiles that copy-paste the raw data verbatim into the fields (especially the 'system_prompt' field, which should be a concise instruction prompt in the second person, not a raw dump).\n"
            "- A good refinement is synthesized, clear, and well-structured.\n\n"
            "You MUST respond ONLY with a valid JSON object matching the following schema. "
            "Do not include any conversational intro/outro text, explanations, or code blocks.\n\n"
            "{\n"
            '  "persona_preservation_score": 8.5,\n'
            '  "speech_style_alignment_score": 9.0,\n'
            '  "accuracy_score": 9.5,\n'
            '  "average_score": 9.0,\n'
            '  "feedback": "Explain what is missing or what was sanitized, and provide specific instructions on how to improve the profile."\n'
            "}"
        )

        messages = [
            {"role": "system", "content": critic_system_prompt},
            {"role": "user", "content": critic_user_content}
        ]

        try:
            result = _ollama_chat_compat(
                model=critic_model,
                messages=messages,
                stream=False,
                format="json",
                think=False,
                options={"temperature": 0.1}
            )

            response_content = result.get("message", {}).get("content", "").strip()

            refined_data = None
            try:
                refined_data = json.loads(response_content)
            except json.JSONDecodeError:
                match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_content, re.DOTALL | re.IGNORECASE)
                if match:
                    try:
                        refined_data = json.loads(match.group(1))
                    except json.JSONDecodeError:
                        pass
                
                if not refined_data:
                    start = response_content.find('{')
                    end = response_content.rfind('}')
                    if start != -1 and end != -1 and end > start:
                        try:
                            refined_data = json.loads(response_content[start:end+1])
                        except json.JSONDecodeError:
                            pass

            if not refined_data:
                print(f"{Fore.YELLOW}[WARNING] Critic model returned invalid JSON structure. Raw response:\n{response_content}")
                return {
                    "persona_preservation_score": 5.0,
                    "speech_style_alignment_score": 5.0,
                    "accuracy_score": 5.0,
                    "average_score": 5.0,
                    "feedback": "Failed to parse critic response JSON."
                }

            # Helper to parse scores from strings/fractions/formats (like "8/10", "8.5/10", "score: 9")
            def parse_score(val):
                if val is None:
                    return 5.0
                if isinstance(val, (int, float)):
                    return float(val)
                s = str(val).strip()
                if '/' in s:
                    parts = s.split('/')
                    try:
                        numerator = float(parts[0].strip())
                        denominator = float(parts[1].strip())
                        if denominator != 0:
                            return (numerator / denominator) * 10.0
                    except (ValueError, TypeError, IndexError):
                        pass
                match = re.search(r'[-+]?\d*\.\d+|\d+', s)
                if match:
                    try:
                        return float(match.group(0))
                    except ValueError:
                        pass
                return 5.0

            # Helper to extract score using keyword matching (case-insensitive fallback)
            def get_any_score(data_dict, pattern_list):
                for key, val in data_dict.items():
                    k_lower = key.lower()
                    if any(pat in k_lower for pat in pattern_list):
                        return parse_score(val)
                return 5.0

            p_score = get_any_score(refined_data, ["persona_preservation", "persona"])
            s_score = get_any_score(refined_data, ["speech_style_alignment", "speech_style", "speech"])
            a_score = get_any_score(refined_data, ["accuracy"])

            # Overwrite/Set refined scores
            refined_data["persona_preservation_score"] = p_score
            refined_data["speech_style_alignment_score"] = s_score
            refined_data["accuracy_score"] = a_score

            if "average_score" in refined_data:
                avg_val = parse_score(refined_data["average_score"])
                if avg_val != 5.0:
                    refined_data["average_score"] = avg_val
                else:
                    refined_data["average_score"] = (p_score + s_score + a_score) / 3.0
            else:
                refined_data["average_score"] = (p_score + s_score + a_score) / 3.0

            if p_score == 5.0 and s_score == 5.0 and a_score == 5.0:
                print(f"{Fore.YELLOW}[WARNING] Critic pass returned default/low score (5.0). Raw response was:\n{response_content}")

            return refined_data

        except Exception as e:
            return {
                "persona_preservation_score": 5.0,
                "speech_style_alignment_score": 5.0,
                "accuracy_score": 5.0,
                "average_score": 5.0,
                "feedback": f"Critic pass failed: {e}"
            }

    @staticmethod
    def refine_character_profile(profile, raw_st_data=None, model=None, interactive=False):
        """
        Uses a local LLM to refine and clean character profile metadata fields.
        Returns the updated profile (modifying fields like alt_names, character_info, backstory, rp_mannerisms).
        """
        from engines.config import get_setting
        from engines.responses import _ollama_chat_compat

        if not profile:
            return profile

        refine_model = model or get_setting("local_utility_model", "llama3.2")
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
            raw_personality = profile.get("raw_personality") or profile.get("personality_type", "")
        if not raw_description:
            raw_description = profile.get("raw_description") or profile.get("backstory", "")
        if not raw_scenario:
            raw_scenario = profile.get("character_info", {}).get("other", "")
        if not raw_mes_example:
            raw_mes_example = profile.get("mes_example", "")

        def clean_raw(text):
            if not text:
                return ""
            return text.replace("{{char}}", char_name).replace("<START>", "").strip()

        raw_personality = clean_raw(raw_personality)
        raw_description = clean_raw(raw_description)
        raw_scenario = clean_raw(raw_scenario)
        raw_mes_example = clean_raw(raw_mes_example)

        # 2. Formulate prompts
        system_prompt = (
            "You are an expert character profile extraction and cleaning assistant.\n"
            "Analyze the provided raw character details and extract structured profile fields.\n"
            "CRITICAL: You must preserve as much distinct persona, unique voice, slang, dialect, and speech style/habits as possible. "
            "Do NOT sanitize, simplify, or homogenize the character's unique traits into generic descriptions.\n"
            "CRITICAL: Do NOT copy-paste the raw description or backstory text verbatim into any fields. The fields must be clean, refined, and synthesized summaries.\n"
            "CRITICAL: We enforce a strict division between behavior and facts to optimize context size:\n"
            "1. The 'system_prompt' field must contain ONLY behavioral, stylistic, formatting, and tone instructions in the second person ('You are...'). E.g., detail formatting quirks, stutters, specific casing, actions, and mannerisms. It MUST NOT contain any biographical backstory, history, or timeline details.\n"
            "2. The 'backstory' field must contain ONLY factual biography, timeline of events, and historical details of the character.\n"
            "3. Extract 2-5 specific secondary facts, world lore elements, or secondary character/NPC details (e.g. specific names of places, past incidents, pets/companions) that are not in the core profile into 'lorebook_entries'. Each entry should specify trigger keys and content.\n\n"
            "Respond ONLY with a valid JSON object matching the following schema.\n"
            "Do not include any conversational intro/outro text, explanations, or code blocks.\n"
            "CRITICAL: Do NOT add any keys to the JSON that are not explicitly specified in the schema below (do NOT add speaking_style, dialogue_examples, etc.).\n"
            "CRITICAL: Do NOT use unescaped double quotes (\") inside your JSON string values. For measurements, use single quotes (e.g., write 4'9' or 4'9 inches instead of 4'9\"). Double quotes inside strings will break the JSON parser.\n\n"
            "{\n"
            '  "system_prompt": "<highly_immersive_behavioral_roleplay_instructions_in_second_person_you_are>",\n'
            '  "personality_type": "<personality_summary_preserving_unique_voice>",\n'
            '  "backstory": "<concise_factual_history_and_biography_timeline>",\n'
            '  "lorebook_entries": [\n'
            '    {\n'
            '      "keys": ["<trigger_word1>", "<trigger_word2>"],\n'
            '      "content": "<specific_secondary_lore_fact_or_npc_details_matching_these_keys_strictly_no_title_or_description_keys>"\n'
            '    }\n'
            '  ],\n'
            '  "rp_mannerisms": ["<mannerism_1>", "<mannerism_2>"],\n'
            '  "appearance": "<appearance_description>",\n'
            '  "gender": "<gender_or_Unknown>",\n'
            '  "age": "<age_or_Unknown>",\n'
            '  "alt_names": "<comma_separated_aliases_or_empty>",\n'
            '  "likes": ["<like_1>", "<like_2>"],\n'
            '  "dislikes": ["<dislike_1>", "<dislike_2>"],\n'
            '  "other": "<refined_rp_scenario_or_other_details>"\n'
            "}"
        )

        user_content = (
            f"Character Name: {char_name}\n"
            f"Raw Personality:\n{raw_personality}\n\n"
            f"Raw Description/Backstory:\n{raw_description}\n\n"
            f"Raw Scenario/Other Details:\n{raw_scenario}\n\n"
            f"Raw Dialogue Examples:\n{raw_mes_example}\n\n"
            "Strict Instructions:\n"
            "1. Extract only facts directly mentioned or clearly implied.\n"
            "2. If age or gender are not mentioned or cannot be inferred, use 'Unknown'.\n"
            "3. Do not invent backstory details. Keep it grounded.\n"
            "4. If 'Raw Personality' is empty, you MUST scan the 'Raw Description/Backstory' field to extract the character's personality details for 'personality_type'.\n"
            "5. Do NOT copy-paste raw description blocks verbatim. You must clean, refine, and synthesize them.\n"
            "6. Keep 'system_prompt' strictly to roleplay style/behavior (no bio), and 'backstory' strictly to biography facts/timeline.\n"
            "7. Extract 2-5 relevant backstory/world info details into 'lorebook_entries'.\n"
            "8. Return ONLY valid JSON."
        )

        correction_system_prompt = (
            "You are an expert character profile extraction and cleaning assistant.\n"
            "You previously generated a refined character profile, but a critic evaluated it and provided feedback on how it can be improved to better preserve the character's distinct persona and speech style.\n"
            "Modify the previous refined profile to incorporate the critic's feedback. "
            "Make sure the character's unique voice, slang, punctuation/formatting quirks (like lowercase, asterisks), and details are preserved as much as possible.\n"
            "CRITICAL: Do NOT copy-paste the raw description or backstory text verbatim. Synthesize it clearly while preserving all critical character mannerisms.\n"
            "CRITICAL: We enforce a strict division between behavior and facts to optimize context size:\n"
            "1. The 'system_prompt' field must contain ONLY behavioral, stylistic, formatting, and tone instructions in the second person ('You are...'). It MUST NOT contain any biographical backstory, history, or timeline details.\n"
            "2. The 'backstory' field must contain ONLY factual biography, timeline of events, and historical details of the character.\n"
            "3. Extract 2-5 specific secondary facts, world lore elements, or secondary character/NPC details (e.g. specific names of places, past incidents, pets/companions) that are not in the core profile into 'lorebook_entries'. Each entry should specify trigger keys and content.\n\n"
            "Respond ONLY with a valid JSON object matching the following schema.\n"
            "Do not include any conversational intro/outro text, explanations, or code blocks.\n"
            "CRITICAL: Do NOT add any keys to the JSON that are not explicitly specified in the schema below (do NOT add speaking_style, dialogue_examples, etc.).\n"
            "CRITICAL: Do NOT use unescaped double quotes (\") inside your JSON string values. For measurements, use single quotes (e.g., write 4'9' or 4'9 inches instead of 4'9\"). Double quotes inside strings will break the JSON parser.\n\n"
            "{\n"
            '  "system_prompt": "<highly_immersive_behavioral_roleplay_instructions_in_second_person_you_are>",\n'
            '  "personality_type": "<personality_summary_preserving_unique_voice>",\n'
            '  "backstory": "<concise_factual_history_and_biography_timeline>",\n'
            '  "lorebook_entries": [\n'
            '    {\n'
            '      "keys": ["<trigger_word1>", "<trigger_word2>"],\n'
            '      "content": "<specific_secondary_lore_fact_or_npc_details_matching_these_keys_strictly_no_title_or_description_keys>"\n'
            '    }\n'
            '  ],\n'
            '  "rp_mannerisms": ["<mannerism_1>", "<mannerism_2>"],\n'
            '  "appearance": "<appearance_description>",\n'
            '  "gender": "<gender_or_Unknown>",\n'
            '  "age": "<age_or_Unknown>",\n'
            '  "alt_names": "<comma_separated_aliases_or_empty>",\n'
            '  "likes": ["<like_1>", "<like_2>"],\n'
            '  "dislikes": ["<dislike_1>", "<dislike_2>"],\n'
            '  "other": "<refined_rp_scenario_or_other_details>"\n'
            "}"
        )

        refusal_triggers = [
            "i cannot fulfill", "against safety guidelines", "i am unable to",
            "cannot generate content", "against policy", "cannot assist with this"
        ]

        best_profile = None
        best_score = -1.0
        attempt = 1
        max_attempts = 4
        
        active_refined_data = None
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        while attempt <= max_attempts:
            print(Fore.CYAN + f"[SYSTEM] (Attempt {attempt}/{max_attempts}) Generating refined profile fields...")
            try:
                result = _ollama_chat_compat(
                    model=refine_model,
                    messages=messages,
                    stream=False,
                    format="json",
                    think=False,
                    options={"temperature": 0.1 if attempt == 1 else 0.3, "num_predict": 2048}
                )

                response_content = result.get("message", {}).get("content", "").strip()

                if any(trigger in response_content.lower() for trigger in refusal_triggers):
                    print(f"{Fore.YELLOW}[WARNING] Local model refused to process character card due to safety constraints.")
                    if best_profile:
                        return best_profile
                    return profile

                refined_data = None
                try:
                    refined_data = json.loads(response_content)
                except json.JSONDecodeError:
                    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_content, re.DOTALL | re.IGNORECASE)
                    if match:
                        try:
                            refined_data = json.loads(match.group(1))
                        except json.JSONDecodeError:
                            pass
                    
                    if not refined_data:
                        start = response_content.find('{')
                        end = response_content.rfind('}')
                        if start != -1 and end != -1 and end > start:
                            try:
                                refined_data = json.loads(response_content[start:end+1])
                            except json.JSONDecodeError:
                                pass

                if not refined_data:
                    print(f"{Fore.YELLOW}[WARNING] Failed to parse AI refinement JSON response.")
                    attempt += 1
                    continue

                active_refined_data = refined_data

                temp_profile = profile.copy()
                if "alt_names" in refined_data and isinstance(refined_data["alt_names"], str):
                    temp_profile["alt_names"] = refined_data["alt_names"].strip()
                if "personality_type" in refined_data and isinstance(refined_data["personality_type"], str):
                    temp_profile["personality_type"] = refined_data["personality_type"].strip()
                if "backstory" in refined_data and isinstance(refined_data["backstory"], str):
                    temp_profile["backstory"] = refined_data["backstory"].strip()
                if "system_prompt" in refined_data and isinstance(refined_data["system_prompt"], str):
                    temp_profile["system_prompt"] = refined_data["system_prompt"].strip()
                if "rp_mannerisms" in refined_data and isinstance(refined_data["rp_mannerisms"], list):
                    temp_profile["rp_mannerisms"] = [m.strip() for m in refined_data["rp_mannerisms"] if isinstance(m, str) and m.strip()]
                
                if "character_info" not in temp_profile:
                    temp_profile["character_info"] = {}
                t_info = temp_profile["character_info"]
                
                if "gender" in refined_data and isinstance(refined_data["gender"], str):
                    t_info["gender"] = refined_data["gender"].strip()
                if "age" in refined_data and isinstance(refined_data["age"], str):
                    t_info["age"] = refined_data["age"].strip()
                if "appearance" in refined_data and isinstance(refined_data["appearance"], str):
                    t_info["appearance"] = refined_data["appearance"].strip()
                if "likes" in refined_data and isinstance(refined_data["likes"], list):
                    t_info["likes"] = [x.strip() for x in refined_data["likes"] if isinstance(x, str) and x.strip()]
                if "dislikes" in refined_data and isinstance(refined_data["dislikes"], list):
                    t_info["dislikes"] = [x.strip() for x in refined_data["dislikes"] if isinstance(x, str) and x.strip()]
                if "other" in refined_data and isinstance(refined_data["other"], str):
                    t_info["other"] = refined_data["other"].strip()
                if "lorebook_entries" in refined_data and isinstance(refined_data["lorebook_entries"], list):
                    temp_profile["lorebook_entries"] = refined_data["lorebook_entries"]

                temp_profile["raw_personality"] = raw_personality
                temp_profile["raw_description"] = raw_description
                temp_profile["mes_example"] = raw_mes_example

                print(Fore.CYAN + f"[SYSTEM] Running Critic Pass to evaluate generated fields...")
                critic_res = CharacterImporter.run_critic_pass(
                    temp_profile,
                    raw_personality,
                    raw_description,
                    raw_scenario,
                    raw_mes_example,
                    model=refine_model
                )

                avg_score = critic_res.get("average_score", 5.0)
                feedback = critic_res.get("feedback", "No feedback provided.")
                p_score = critic_res.get("persona_preservation_score", 5.0)
                s_score = critic_res.get("speech_style_alignment_score", 5.0)
                a_score = critic_res.get("accuracy_score", 5.0)

                print(Fore.CYAN + f"[SYSTEM] AI Critic Score: {avg_score:.2f}/10.0 (Persona: {p_score}/10, Speech Style: {s_score}/10, Accuracy: {a_score}/10)")
                print(Fore.CYAN + f"[SYSTEM] Critic Feedback: {feedback}")

                if avg_score > best_score:
                    best_score = avg_score
                    best_profile = temp_profile

                if best_score >= 8.5:
                    print(Fore.GREEN + f"[SUCCESS] Critique passed threshold (8.5). Merging refined fields.")
                    return best_profile

                if attempt == max_attempts:
                    break

                if interactive:
                    print(Fore.YELLOW + f"\nRefinement did not meet target quality (8.5/10.0).")
                    print("Options:")
                    print("  [1] Retry refinement with Critic Feedback (AI will adjust content)")
                    print("  [2] Accept and merge this version anyway")
                    print("  [3] Skip AI refinement (keep basic card import)")

                    choice = ""
                    while choice not in ["1", "2", "3"]:
                        choice = input("Select an option [1-3] (default: 1): ").strip()
                        if not choice:
                            choice = "1"

                    if choice == "2":
                        print(Fore.GREEN + "[SUCCESS] Merging current refined version.")
                        return temp_profile
                    elif choice == "3":
                        print(Fore.YELLOW + "[INFO] Skipping AI refinement, reverting to baseline.")
                        return profile

                    print(Fore.CYAN + "[SYSTEM] Retrying refinement with feedback...")
                else:
                    print(Fore.YELLOW + f"[INFO] Quality score {avg_score:.2f} is below 8.5. Retrying automatically...")

                correction_user_content = (
                    f"Character Name: {char_name}\n"
                    f"--- RAW SOURCE DATA ---\n"
                    f"Raw Personality:\n{raw_personality}\n\n"
                    f"Raw Description/Backstory:\n{raw_description}\n\n"
                    f"Raw Scenario/Other Details:\n{raw_scenario}\n\n"
                    f"Raw Dialogue Examples:\n{raw_mes_example}\n\n"
                    f"--- PREVIOUS ATTEMPT ---\n"
                    f"{json.dumps(active_refined_data, indent=2)}\n\n"
                    f"--- CRITIC FEEDBACK ---\n"
                    f"Critic Score: {avg_score:.2f}/10.0\n"
                    f"Feedback: {feedback}\n\n"
                    "Please refine the profile again, strictly addressing the critic feedback to ensure high fidelity and distinct persona preservation. Return ONLY valid JSON."
                )

                messages = [
                    {"role": "system", "content": correction_system_prompt},
                    {"role": "user", "content": correction_user_content}
                ]
                attempt += 1

            except Exception as e:
                print(f"{Fore.YELLOW}[WARNING] AI refinement attempt {attempt} failed: {e}.")
                attempt += 1

        if best_profile:
            print(Fore.YELLOW + f"[WARNING] AI refinement did not achieve target score (8.5/10.0). Using best attempt (Score: {best_score:.2f}/10.0).")
            return best_profile

        return profile

    @staticmethod
    def save_profile(profile, filename=None):
        """Saves the converted profile to the profiles/ directory."""
        if not profile or not profile.get("name"):
            return False

        from engines.utilities import sanitize_profile_name

        # Determine the base filename prefix/identifier
        if filename:
            base_ident = os.path.splitext(os.path.basename(filename))[0]
        else:
            safe_name = sanitize_profile_name(profile["name"])
            import hashlib
            hash_input = f"{profile.get('name', '')}|{profile.get('system_prompt', '')}|{profile.get('backstory', '')}"
            profile_hash = hashlib.md5(hash_input.encode('utf-8')).hexdigest()[:8]
            base_ident = f"{safe_name}_{profile_hash}"
            filename = f"{base_ident}.json"

        # Ensure we only have the basename of the filename
        filename = os.path.basename(filename)

        if not filename.endswith(".json"):
            filename += ".json"

        # If there are lorebook entries in the profile, extract them and save to a separate lorebook file
        lorebook_entries = profile.pop("lorebook_entries", None)
        if lorebook_entries and isinstance(lorebook_entries, list):
            lorebook_data = {
                "entries": []
            }
            for idx, entry in enumerate(lorebook_entries):
                if isinstance(entry, dict) and "keys" in entry and "content" in entry:
                    seen_keys = []
                    for k in entry.get("keys", []):
                        k_clean = str(k).strip()
                        if k_clean and k_clean not in seen_keys:
                            seen_keys.append(k_clean)
                    lorebook_data["entries"].append({
                        "id": str(idx + 1),
                        "keys": seen_keys,
                        "content": str(entry["content"]).strip(),
                        "enabled": True,
                        "insertion_order": 50
                    })
            
            if lorebook_data["entries"]:
                os.makedirs("lorebooks", exist_ok=True)
                lorebook_file_path = os.path.join("lorebooks", f"{base_ident}.json")
                try:
                    with open(lorebook_file_path, "w", encoding="utf-8") as lf:
                        json.dump(lorebook_data, lf, indent=4, ensure_ascii=False)
                    profile["lorebook_path"] = f"lorebooks/{base_ident}.json"
                    print(f"{Fore.GREEN}[SUCCESS] Saved custom character lorebook to lorebooks/{base_ident}.json")
                except Exception as e:
                    print(f"{Fore.YELLOW}[WARNING] Failed to save custom character lorebook: {e}")

        # Construct target path relative to profiles directory
        profiles_dir = os.path.abspath("profiles")
        target_path = os.path.abspath(os.path.join(profiles_dir, filename))

        # Security check: Ensure the target path is still within the profiles directory
        if not target_path.startswith(profiles_dir):
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

def import_character(source_path, refine=False, model=None, interactive=False):
    """Main entry point for importing a character with optional AI refinement."""
    data = None
    avatar_path = "img/No_Image_Error.png"

    if source_path.lower().endswith((".png", ".webp")):
        data = CharacterImporter.extract_from_png(source_path)
        if data and "name" in data:
            char_name = data["name"]
            
            # Compute a hash of the raw card data to prevent image name collision
            import hashlib
            hash_input = f"{data.get('name', '')}|{data.get('personality', '')}|{data.get('description', '')}|{data.get('mes_example', '')}"
            card_hash = hashlib.md5(hash_input.encode('utf-8')).hexdigest()[:8]
            
            # Create a safe filename for the image
            safe_name = re.sub(r'[^\w\s-]', '', char_name).strip().replace(' ', '_')
            ext = os.path.splitext(source_path)[1]
            dest_image = os.path.join("img", f"{safe_name}_{card_hash}{ext}")

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
            from engines.config import get_setting
            refine_model = model or get_setting("local_utility_model", "llama3.2")
            print(Fore.CYAN + f"[SYSTEM] Running AI profile refinement using local model '{refine_model}'...")
            
            try:
                with open(save_path, "r", encoding="utf-8") as f:
                    saved_profile = json.load(f)
                
                refined_profile = CharacterImporter.refine_character_profile(
                    saved_profile,
                    raw_st_data=data,
                    model=refine_model,
                    interactive=interactive
                )
                
                # Overwrite the saved profile with refined contents
                CharacterImporter.save_profile(refined_profile, filename=os.path.basename(save_path))
                print(f"{Fore.GREEN}[SUCCESS] AI refinement complete. Refined fields merged successfully.")
            except Exception as e:
                print(f"{Fore.YELLOW}[WARNING] AI refinement failed: {e}. Keeping the baseline rule-based profile.")
        else:
            print(f"{Fore.YELLOW}[INFO] Conversion may be imperfect. It is recommended to run AI refinement or review the profile.")
            
        return save_path
    return None
