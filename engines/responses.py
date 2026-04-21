"""
Core LLM interaction engine.
Handles streaming responses, sentiment parsing, and relationship score updates.
"""

import re
import json
import traceback
import ollama
import requests
from datetime import datetime
from engines.memory_v2 import memory_manager
from engines.config import get_setting
from engines.narrative_pipeline import (
    append_turn_telemetry,
    build_canonical_state,
    build_narrative_plan,
    get_pipeline_flags,
    needs_critic_pass,
    rank_candidates,
    score_candidate,
    render_pipeline_context,
    retrieve_memory_stack,
    update_narrative_state,
)
from engines.prompts import build_system_prompt
from engines.lorebook import load_lorebook, scan_for_lore


def _normalize_for_duplicate_check(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return normalized


def _is_duplicate_reply(candidate: str, previous_replies: list[str]) -> bool:
    candidate_norm = _normalize_for_duplicate_check(candidate)
    if not candidate_norm:
        return False
    previous_norm = {_normalize_for_duplicate_check(reply) for reply in previous_replies if reply}
    return candidate_norm in previous_norm

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


def _call_llm_once(messages: list, model: str, remote_url: str = None, temperature: float = 0.8, max_tokens: int = 1024) -> str:
    """Single-turn non-streaming helper used by candidate/reranker pipeline stages."""
    if remote_url:
        full_url = f"{remote_url.rstrip('/')}/chat"
        payload = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        response = requests.post(full_url, json=payload, stream=False, timeout=90)
        response.raise_for_status()
        result = response.json()
        if isinstance(result, dict):
            if "choices" in result and result["choices"]:
                return result["choices"][0]["message"]["content"].strip()
            if "message" in result and isinstance(result["message"], dict):
                return result["message"].get("content", "").strip()
        return ""

    result = ollama.chat(
        model=model,
        messages=messages,
        stream=False,
        options={"temperature": temperature},
    )
    return result["message"]["content"].strip()


def _generate_candidate_replies(messages: list, model: str, remote_url: str, candidate_count: int) -> list[str]:
    candidates = []
    for index in range(max(1, candidate_count)):
        temperature = min(1.0, 0.75 + (0.08 * index))
        try:
            candidate = _call_llm_once(messages, model=model, remote_url=remote_url, temperature=temperature)
        except Exception:
            candidate = ""
        if candidate:
            candidates.append(candidate)
    return candidates


def _rewrite_with_critic(messages: list, original_reply: str, model: str, remote_url: str, interaction_mode: str) -> str:
    repair_instruction = (
        "Repair the assistant reply to remain strictly in-character, preserve continuity, "
        "and push the story forward with one concrete beat. "
        "Do not mention being an AI system or model."
    )
    if interaction_mode == "rp":
        repair_instruction += " Include dialogue and/or narration style naturally."
    critic_messages = list(messages) + [
        {
            "role": "system",
            "content": repair_instruction,
        },
        {
            "role": "assistant",
            "content": original_reply,
        },
    ]
    try:
        rewritten = _call_llm_once(critic_messages, model=model, remote_url=remote_url, temperature=0.5)
        return rewritten or original_reply
    except Exception:
        return original_reply

def get_respond_stream(user_input: str, profile: dict, should_obey: bool | None = None, profile_path: str = None, system_extra_info: str = None, history_profile_name: str = None, is_regeneration: bool = False):
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
        is_regeneration (bool): If True, we are regenerating the last AI message.

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
    prompt_history = list(history) if history else []

    # 1. Lorebook Scanning
    # Scan recent history (last 3 messages) + current user input for keywords
    lore_file = profile.get("lorebook_path") or "lorebooks/default.json"
    lorebook_data = load_lorebook(lore_file)
    recent_context = history[-3:] + [{'role': 'user', 'content': user_input}]
    activated_lore = scan_for_lore(recent_context, lorebook_data)

    # Determine relationship score and interaction mode
    rel_score = profile.get("relationship_score", 0)
    interaction_mode = get_setting("interaction_mode", "rp")
    pipeline_flags = get_pipeline_flags()
    canonical_state = None
    memory_stack = None
    narrative_plan = None

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

    if pipeline_flags["enabled"]:
        metadata = full_data.get("metadata", {})
        canonical_state = build_canonical_state(profile, metadata, user_input) if pipeline_flags["state"] else None

        if pipeline_flags["memory"]:
            full_history_for_memory = memory_manager.load_history(history_profile_name)
            memory_stack = retrieve_memory_stack(
                full_history_for_memory,
                user_input,
                short_limit=max(6, min(20, limit)),
            )

        if pipeline_flags["planner"] and canonical_state is not None:
            narrative_plan = build_narrative_plan(canonical_state, user_input, interaction_mode)

        if canonical_state is not None:
            pipeline_context = render_pipeline_context(canonical_state, memory_stack, narrative_plan)
            system_extra_info = f"{system_extra_info}\n\n{pipeline_context}"

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
    regeneration_previous_replies = []

    if is_regeneration:
        # If regenerating, we want the LLM to provide a new response to the LAST user message.
        # Remove the trailing assistant turn only from the prompt copy, not from persistent history.
        if prompt_history and prompt_history[-1].get("role") == "assistant":
            prior_assistant = prompt_history[-1]
            alternatives = prior_assistant.get("alternatives", [])
            if alternatives:
                regeneration_previous_replies = [alt for alt in alternatives if alt]
            elif prior_assistant.get("content"):
                regeneration_previous_replies = [prior_assistant.get("content")]
            prompt_history.pop()
        messages.extend(prompt_history)
        # The user_input passed in is the last user message.
        if (
            not prompt_history
            or prompt_history[-1].get("role") != "user"
            or prompt_history[-1].get("content") != user_input
        ):
            messages.append({'role': 'user', 'content': user_input})

        if regeneration_previous_replies:
            replay_block = "\n".join(f"- {reply[:220]}" for reply in regeneration_previous_replies[-3:])
            messages[0]["content"] = (
                f"{messages[0]['content']}\n\n"
                "[REGENERATION DIVERSITY CONSTRAINT]\n"
                "Generate a substantially different alternative response while preserving canon and scene continuity.\n"
                "Do not paraphrase the same response structure.\n"
                f"Previous assistant attempts:\n{replay_block}\n"
            )
    else:
        messages.extend(prompt_history)
        messages.append({'role': 'user', 'content': user_input})

    full_reply = ""
    selected_metrics = {}
    candidate_metrics = []
    critic_applied = False

    try:
        if pipeline_flags["enabled"] and (pipeline_flags["candidates"] or pipeline_flags["critic"]):
            if canonical_state is None:
                canonical_state = build_canonical_state(profile, full_data.get("metadata", {}), user_input)

            if pipeline_flags["candidates"]:
                candidate_replies = _generate_candidate_replies(
                    messages,
                    model=model,
                    remote_url=remote_url,
                    candidate_count=pipeline_flags["candidate_count"],
                )
                if not candidate_replies:
                    candidate_replies = [_call_llm_once(messages, model=model, remote_url=remote_url, temperature=0.8)]

                ranked = rank_candidates(candidate_replies, canonical_state, narrative_plan, interaction_mode)
                best = ranked[0]
                if is_regeneration and regeneration_previous_replies:
                    for ranked_item in ranked:
                        if not _is_duplicate_reply(ranked_item["text"], regeneration_previous_replies):
                            best = ranked_item
                            break
                    else:
                        replay_block = "\n".join(f"- {reply[:220]}" for reply in regeneration_previous_replies[-3:])
                        diversify_messages = list(messages) + [
                            {
                                "role": "system",
                                "content": (
                                    "Regeneration output must be materially different from previous attempts while preserving canon. "
                                    "Do not paraphrase the same structure.\n"
                                    f"Previous attempts:\n{replay_block}"
                                ),
                            }
                        ]
                        diversified = _call_llm_once(
                            diversify_messages,
                            model=model,
                            remote_url=remote_url,
                            temperature=1.05,
                        ).strip()
                        if diversified:
                            best = {
                                "index": -1,
                                "text": diversified,
                                "metrics": score_candidate(diversified, canonical_state, narrative_plan, interaction_mode),
                            }
                            ranked = [best] + ranked

                reply = best["text"]
                selected_metrics = best["metrics"]
                candidate_metrics = [row["metrics"] for row in ranked]
            else:
                reply = _call_llm_once(messages, model=model, remote_url=remote_url, temperature=0.8).strip()
                selected_metrics = score_candidate(reply, canonical_state, narrative_plan, interaction_mode)
                candidate_metrics = [selected_metrics]

            if pipeline_flags["critic"] and needs_critic_pass(reply, interaction_mode):
                critic_applied = True
                reply = _rewrite_with_critic(
                    messages,
                    original_reply=reply,
                    model=model,
                    remote_url=remote_url,
                    interaction_mode=interaction_mode,
                )

            full_reply = reply
            chunk_size = 60
            for index in range(0, len(reply), chunk_size):
                yield reply[index:index + chunk_size]
        else:
            # Handle Remote LLM Request
            generation_temperature = 0.95 if is_regeneration else 0.8
            if remote_url:
                full_url = f"{remote_url.rstrip('/')}/chat"
                payload = {"messages": messages, "temperature": generation_temperature, "max_tokens": 1024}
                response = requests.post(full_url, json=payload, stream=True, timeout=60)
                response.raise_for_status()
                stream = response.iter_content(chunk_size=None, decode_unicode=True)
            # Handle Local Ollama Request
            else:
                ollama_stream = ollama.chat(
                    model=model,
                    messages=messages,
                    stream=True,
                    options={"temperature": generation_temperature},
                )

                def ollama_gen():
                    for chunk in ollama_stream:
                        if isinstance(chunk, dict):
                            message = chunk.get("message", {})
                            if isinstance(message, dict):
                                content = message.get("content", "")
                                if content:
                                    yield content
                        elif isinstance(chunk, list):
                            for nested in chunk:
                                if isinstance(nested, dict):
                                    message = nested.get("message", {})
                                    if isinstance(message, dict):
                                        content = message.get("content", "")
                                        if content:
                                            yield content
                stream = ollama_gen()

            # For regeneration, buffer first so we can detect/retry repetition before emitting UI chunks.
            if is_regeneration:
                for content in stream:
                    full_reply += content

                buffered_reply = full_reply.strip()
                if (
                    regeneration_previous_replies
                    and buffered_reply
                    and _is_duplicate_reply(buffered_reply, regeneration_previous_replies)
                ):
                    retry_messages = list(messages) + [
                        {
                            "role": "system",
                            "content": (
                                "Your previous attempt matched an earlier response. "
                                "Generate a materially different continuation that still fits continuity."
                            ),
                        }
                    ]
                    try:
                        buffered_reply = _call_llm_once(
                            retry_messages,
                            model=model,
                            remote_url=remote_url,
                            temperature=1.0,
                        ).strip() or buffered_reply
                    except Exception:
                        pass

                full_reply = buffered_reply
                chunk_size = 60
                for index in range(0, len(full_reply), chunk_size):
                    yield full_reply[index:index + chunk_size]
            else:
                # Iterate through the generator stream — yield content directly, no tag filtering needed
                for content in stream:
                    full_reply += content
                    yield content

        # Regeneration should be idempotent: do not re-score sentiment or mutate relationship score.
        if is_regeneration:
            score_change = 0
        else:
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

        if is_regeneration:
            # Multi-response Logic: Keep all responses in an 'alternatives' list
            if full_history and full_history[-1].get("role") == "assistant":
                last_msg = full_history[-1]
                if "alternatives" not in last_msg:
                    last_msg["alternatives"] = [last_msg.get("content", "")]

                last_msg["alternatives"].append(reply)
                last_msg["selected_index"] = len(last_msg["alternatives"]) - 1
                last_msg["content"] = reply # Set the visible content to the newest one
            else:
                # Fallback if history state is weird
                full_history.append({'role': 'assistant', 'content': reply})
        else:
            full_history.append({'role': 'user', 'content': user_input})
            full_history.append({'role': 'assistant', 'content': reply})

        memory_manager.save_history(history_profile_name, full_history, mood_score=rel_score, current_scene=new_scene)

        if pipeline_flags["enabled"] and pipeline_flags["state"]:
            previous_state = full_data.get("metadata", {}).get("narrative_state", {})
            new_state = update_narrative_state(
                previous_state,
                user_input=user_input,
                assistant_reply=reply,
                sentiment_score=score_change,
                current_scene=new_scene,
            )
            memory_manager.update_narrative_state(
                history_profile_name,
                new_state,
                turn_metrics=selected_metrics,
            )

        append_turn_telemetry(
            history_profile_name,
            {
                "pipeline_enabled": pipeline_flags["enabled"],
                "is_regeneration": is_regeneration,
                "mode": interaction_mode,
                "candidate_count": len(candidate_metrics),
                "candidate_totals": [metrics.get("total", 0) for metrics in candidate_metrics],
                "selected_metrics": selected_metrics,
                "critic_applied": critic_applied,
                "memory_flags": (memory_stack or {}).get("continuity_flags", []),
                "plan": narrative_plan or {},
            },
        )

    except Exception as e:
        if get_setting("debug_mode", False):
            yield f"\n[BRAIN ERROR] {traceback.format_exc()}"
        else:
            yield f"\n[BRAIN ERROR] {str(e)}"

def get_respond(user_input: str, profile: dict, should_obey: bool = True, profile_path: str = None, is_regeneration: bool = False) -> str:
    """Non-streaming version of the response generator."""
    full_response = ""
    for chunk in get_respond_stream(user_input, profile, should_obey, profile_path, is_regeneration=is_regeneration):
        full_response += chunk
    return full_response
