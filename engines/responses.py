"""
Core LLM interaction engine.
Handles streaming responses, sentiment parsing, and relationship score updates.
"""

import re
import json
import ollama
import requests
from datetime import datetime
from engines.memory_v2 import memory_manager
from engines.config import get_setting
from engines.prompts import build_system_prompt
from engines.lorebook import load_lorebook, scan_for_lore

def apply_mood_decay(profile_path: str, history_profile_name: str):
    """
    Calculates time passed since the last interaction and decays the relationship
    score back towards 0 (neutral) proportionally.

    Args:
        profile_path (str): Path to the companion's .json profile.
        history_profile_name (str): The name of the companion for history purposes.

    Returns:
        tuple: (decay_amount, new_score) if decay happened, else None.
    """
    last_time = memory_manager.get_last_timestamp(history_profile_name)
    if not last_time:
        return 0, 0

    now = datetime.now()
    diff = now - last_time
    hours_passed = diff.total_seconds() / 3600

    # Only apply decay if at least 5 minutes have passed
    if hours_passed < (5 / 60):
        return 0, 0

    try:
        with open(profile_path, "r", encoding="UTF-8") as f:
            data = json.load(f)

        current_score = data.get("relationship_score", 0)
        if current_score == 0:
            return 0, 0

        # Relationship fades by 5% every hour (decay_factor = 0.95)
        decay_factor = 0.95
        new_score_float = current_score * (decay_factor ** hours_passed)
        new_score = int(round(new_score_float))

        if current_score != new_score:
            decay_amount = abs(current_score - new_score)
            data["relationship_score"] = new_score
            with open(profile_path, "w", encoding="UTF-8") as f:
                json.dump(data, f, indent=4)
            return decay_amount, new_score

    except Exception as e:
        print(f"Error applying mood decay: {e}")

    return 0, 0

def update_profile_score(profile_path: str, score_change: int):
    """
    Persists a change to the companion's relationship score.

    Args:
        profile_path (str): Path to the .json profile.
        score_change (int): Amount to add or subtract (-100 to 100 cap).
    """
    try:
        with open(profile_path, "r", encoding="UTF-8") as f:
            data = json.load(f)

        current_score = data.get("relationship_score", 0)
        new_score = max(-100, min(100, current_score + score_change))
        data["relationship_score"] = new_score

        with open(profile_path, "w", encoding="UTF-8") as f:
            json.dump(data, f, indent=4)

    except Exception as e:
        print(f"Error updating profile score: {e}")

def get_sentiment_score(user_input: str, model: str, remote_url: str = None, profile: dict = None) -> int:
    """
    Makes a separate lightweight LLM call to score the sentiment of the user's message.
    Runs after the main stream completes, so it never blocks or pollutes the response.

    Returns:
        int: A score from -5 to +5.
    """
    char_name = profile.get("name", "the character") if profile else "the character"
    messages = [
        {
            "role": "system",
            "content": (
                f'You are {char_name}. Rate how the user\'s message makes you feel. '
                f'Reply with ONLY this JSON and nothing else: {{"rel": N}} '
                f'where N is an integer from -5 (very negative) to +5 (very positive).'
            )
        },
        {"role": "user", "content": user_input}
    ]
    try:
        if remote_url:
            full_url = f"{remote_url.rstrip('/')}/chat"
            payload = {"messages": messages, "temperature": 0.0, "max_tokens": 20}
            response = requests.post(full_url, json=payload, stream=False, timeout=10)
            text = response.text
        else:
            result = ollama.chat(model=model, messages=messages, stream=False)
            text = result['message']['content']

        match = re.search(r'"rel":\s*([+-]?\d+)', text)
        if match:
            return max(-5, min(5, int(match.group(1))))
    except Exception:
        pass
    return 0

def generate_summary(messages: list, model: str, remote_url: str = None, user_name: str = "User", char_name: str = "Assistant") -> str:
    """
    Generates a concise summary of the provided conversation history.

    Args:
        messages (list): The chat history to summarize.
        model (str): The model to use for summarization.
        remote_url (str, optional): The URL for remote LLM inference.
        user_name (str): The name of the user persona.
        char_name (str): The name of the character persona.

    Returns:
        str: The generated summary.
    """
    summary_prompt = (
        f"Summarize the following conversation history between {user_name} and {char_name} concisely in bullet points. "
        "Focus on: "
        "- Key narrative events and plot points.\n"
        "- Character emotions, mood changes, and relationship shifts.\n"
        "- Any important information or decisions made.\n"
        f"Refer to the participants as {user_name} and {char_name}. "
        "Keep the summary short and informative. Use [bold yellow] Memory Core Summary [/bold yellow] as header."
    )

    formatted_history = ""
    for msg in messages:
        role = msg.get("role", "unknown")
        name = user_name if role == "user" else char_name
        content = msg.get("content", "")
        formatted_history += f"{name.upper()}: {content}\n"


    summary_messages = [
        {"role": "system", "content": summary_prompt},
        {"role": "user", "content": f"History to summarize:\n{formatted_history}"}
    ]

    try:
        if remote_url:
            full_url = f"{remote_url.rstrip('/')}/chat"
            # OpenAI-compatible API call
            payload = {"messages": summary_messages, "temperature": 0.3, "max_tokens": 500}
            response = requests.post(full_url, json=payload, stream=False, timeout=60)
            result = response.json()
            # Remote API might return differently, adjust as needed
            if 'choices' in result:
                return result['choices'][0]['message']['content'].strip()
            return result.get('message', {}).get('content', 'Error generating remote summary.')
        else:
            result = ollama.chat(model=model, messages=summary_messages, stream=False)
            return result['message']['content'].strip()
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def update_rolling_summary(existing_core: str, new_messages: list, model: str, 
                           remote_url: str = None, user_name: str = "User", 
                           char_name: str = "Assistant") -> str:
    """
    Consolidates the existing Memory Core with new conversation messages.
    """
    summary_prompt = (
        f"You are updating the Memory Core for {char_name}. "
        f"Below is the existing Memory Core summary and a set of new messages between {user_name} and {char_name}. "
        "Create a NEW, consolidated Memory Core that incorporates the new events while keeping the total length concise. "
        "Maintain bullet points. Focus on character growth and key plot developments. "
        "Always start with '[bold yellow] Memory Core Summary [/bold yellow]'."
    )
    
    formatted_new_history = ""
    for msg in new_messages:
        role = msg.get("role", "unknown")
        name = user_name if role == "user" else char_name
        content = msg.get("content", "")
        formatted_new_history += f"{name.upper()}: {content}\n"

    input_content = (
        f"EXISTING MEMORY CORE:\n{existing_core}\n\n"
        f"NEW MESSAGES TO CONSOLIDATE:\n{formatted_new_history}"
    )

    summary_messages = [
        {"role": "system", "content": summary_prompt},
        {"role": "user", "content": input_content}
    ]

    try:
        if remote_url:
            full_url = f"{remote_url.rstrip('/')}/chat"
            payload = {"messages": summary_messages, "temperature": 0.3, "max_tokens": 600}
            response = requests.post(full_url, json=payload, stream=False, timeout=60)
            result = response.json()
            if 'choices' in result:
                return result['choices'][0]['message']['content'].strip()
            return result.get('message', {}).get('content', 'Error updating remote rolling summary.')
        else:
            result = ollama.chat(model=model, messages=summary_messages, stream=False)
            return result['message']['content'].strip()
    except Exception as e:
        return f"Error updating rolling summary: {str(e)}"

def get_respond_stream(user_input: str, profile: dict, should_obey: bool | None = None, profile_path: str = None, system_extra_info: str = None, history_profile_name: str = None):
    """
    Generates a streaming response from the LLM (Local Ollama or Remote API).
    Parses sentiment tags [REL: +X] to update relationship status in real-time.

    Args:
        user_input (str): The raw text from the user.
        profile (dict): The companion's profile data.
        should_obey (bool): Result of the mood engine's decision.
        profile_path (str): Path to the profile file (for score updates).
        system_extra_info (str): Temporary context instructions.
        history_profile_name (str): The name of the profile for history management.

    Yields:
        str: Chunks of text as they are generated by the LLM.
    """
    name = profile.get("name")
    model = profile.get("llm_model", get_setting("default_llm_model", "llama3"))
    remote_url = get_setting("remote_llm_url")

    if not history_profile_name:
        history_profile_name = name # Fallback to display name

    # Load history and metadata
    full_data = memory_manager.get_full_data(history_profile_name)
    current_scene = full_data.get("metadata", {}).get("current_scene", "Unknown Location")
    memory_core = full_data.get("metadata", {}).get("memory_core", "")
    
    limit = get_setting("memory_limit", 15)
    history = memory_manager.load_history(history_profile_name, limit=limit)

    # 1. Lorebook Scanning
    # Scan recent history (last 3 messages) + current user input for keywords
    lore_file = profile.get("lorebook_path") or "lorebooks/default.json"
    lorebook_data = load_lorebook(lore_file)
    recent_context = history[-3:] + [{'role': 'user', 'content': user_input}]
    activated_lore = scan_for_lore(recent_context, lorebook_data)

    # Determine relationship score and interaction mode
    rel_score = profile.get("relationship_score", 0)
    interaction_mode = get_setting("interaction_mode", "rp")

    # Handle Dynamic Scene Context and Memory Core
    scene_instruction = f"CURRENT SCENE: {current_scene}. Keep this context in mind."
    if interaction_mode == "rp":
        scene_instruction += " If the location or activity changes significantly, append [SCENE: new location] at the VERY end of your response."
    
    if memory_core:
        # Prepend the Memory Core to provide long-term context
        scene_instruction = f"{memory_core}\n\n{scene_instruction}"

    if activated_lore:
        # Prepend activated lore to provide immediate world/character context
        scene_instruction = f"{activated_lore}\n\n{scene_instruction}"

    if system_extra_info:
        system_extra_info = f"{scene_instruction}\n{system_extra_info}"
    else:
        system_extra_info = scene_instruction

    # Set behavioral requirements based on the Mood Engine's 'should_obey' decision
    if should_obey is not None:
        if not should_obey:
            action_req = "MUST REFUSE the user's request."
            tone_mod = profile.get("bad_prompt_modifyer", "Refuse creatively.")
        else:
            action_req = "MUST AGREE to the user's request."
            tone_mod = profile.get("good_prompt_modifyer", "Agree and assist.")
    else:
        action_req = "Respond normally."
        tone_mod = "Maintain a balanced tone."

    # Construct the master system instruction
    system_content = build_system_prompt(profile, rel_score, action_req, tone_mod, interaction_mode, system_extra_info)

    # Compile message list for the LLM
    messages = [{'role': 'system', 'content': system_content}]
    messages.extend(history)
    messages.append({'role': 'user', 'content': user_input})

    full_reply = ""

    try:
        # Handle Remote LLM Request
        if remote_url:
            full_url = f"{remote_url.rstrip('/')}/chat"
            payload = {"messages": messages, "temperature": 0.8, "max_tokens": 1024}
            response = requests.post(full_url, json=payload, stream=True, timeout=60)
            response.raise_for_status()
            stream = response.iter_content(chunk_size=None, decode_unicode=True)
        # Handle Local Ollama Request
        else:
            ollama_stream = ollama.chat(model=model, messages=messages, stream=True)
            def ollama_gen():
                for chunk in ollama_stream:
                    yield chunk['message']['content']
            stream = ollama_gen()

        # Iterate through the generator stream — yield content directly, no tag filtering needed
        for content in stream:
            full_reply += content
            yield content

        # Score the user's message sentiment via a separate dedicated call
        score_change = get_sentiment_score(user_input, model, remote_url, profile)
        reply = full_reply.strip()

        # Parse for scene updates
        new_scene = current_scene
        scene_match = re.search(r'\[SCENE:\s*(.*?)\]', reply)
        if scene_match:
            new_scene = scene_match.group(1).strip()
            # Clean the tag from the final saved history
            reply = re.sub(r'\[SCENE:\s*.*?\]', '', reply).strip()

        # Persist the relationship update
        if profile_path and score_change != 0:
            update_profile_score(profile_path, score_change)

        # Save the interaction to persistent memory
        full_history = memory_manager.load_history(history_profile_name)
        full_history.append({'role': 'user', 'content': user_input})
        full_history.append({'role': 'assistant', 'content': reply})
        memory_manager.save_history(history_profile_name, full_history, mood_score=rel_score, current_scene=new_scene)

    except Exception as e:
        yield f"\n[BRAIN ERROR] {str(e)}"

def get_respond(user_input: str, profile: dict, should_obey: bool = True, profile_path: str = None) -> str:
    """Non-streaming version of the response generator."""
    full_response = ""
    for chunk in get_respond_stream(user_input, profile, should_obey, profile_path):
        full_response += chunk
    return full_response
