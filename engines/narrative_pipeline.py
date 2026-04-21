"""
Narrative pipeline helpers for roleplay quality improvements.
These utilities are feature-flagged by callers and safe to keep idle by default.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

from engines.config import get_setting
from engines.utilities import sanitize_profile_name


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9']+", text.lower()) if len(token) > 2}


def _score_overlap(text: str, reference_tokens: set[str]) -> int:
    if not reference_tokens:
        return 0
    return len(_tokenize(text) & reference_tokens)


def get_pipeline_flags() -> dict:
    return {
        "enabled": get_setting("overhaul_pipeline_enabled", False),
        "instrumentation": get_setting("overhaul_instrumentation_enabled", False),
        "state": get_setting("overhaul_state_enabled", False),
        "memory": get_setting("overhaul_memory_enabled", False),
        "planner": get_setting("overhaul_planner_enabled", False),
        "candidates": get_setting("overhaul_candidates_enabled", False),
        "critic": get_setting("overhaul_critic_enabled", False),
        "candidate_count": max(1, int(get_setting("overhaul_candidate_count", 3))),
        "style_profile": get_setting("overhaul_style_profile", "balanced"),
    }


def build_canonical_state(profile: dict, metadata: dict, user_input: str) -> dict:
    narrative_state = metadata.get("narrative_state") or {}
    unresolved_threads = narrative_state.get("unresolved_threads", [])
    return {
        "immutable": {
            "name": profile.get("name", "Assistant"),
            "personality_type": profile.get("personality_type", "Unknown"),
            "backstory": profile.get("backstory", ""),
            "mannerisms": profile.get("rp_mannerisms", []),
            "hard_constraints": profile.get("hard_constraints", []),
        },
        "mutable": {
            "relationship_score": profile.get("relationship_score", 0),
            "current_scene": metadata.get("current_scene", "Unknown Location"),
            "current_goal": narrative_state.get("current_goal", "Stay in character and move the interaction forward."),
            "last_emotional_shift": narrative_state.get("last_emotional_shift", "steady"),
            "unresolved_threads": unresolved_threads[-8:],
            "last_user_intent": user_input[:180],
            "style_profile": get_setting("overhaul_style_profile", "balanced"),
        },
    }


def retrieve_memory_stack(full_history: list, user_input: str, short_limit: int = 12, episodic_limit: int = 6, semantic_limit: int = 6) -> dict:
    history = full_history or []
    short_term = history[-short_limit:]
    remainder = history[:-short_limit] if len(history) > short_limit else []
    query_tokens = _tokenize(user_input)

    semantic_pool = []
    for index, msg in enumerate(history):
        content = msg.get("content", "")
        score = _score_overlap(content, query_tokens)
        if score > 0:
            semantic_pool.append((score, index, msg))
    semantic_pool.sort(key=lambda row: (row[0], row[1]), reverse=True)
    semantic_retrieval = [row[2] for row in semantic_pool[:semantic_limit]]

    episodic = []
    for msg in reversed(remainder):
        content = msg.get("content", "")
        if re.search(r"\b(scene|promise|plan|later|remember|quest|goal)\b", content, flags=re.IGNORECASE):
            episodic.append(msg)
        if len(episodic) >= episodic_limit:
            break
    episodic.reverse()

    contradictions = []
    if "actually" in user_input.lower() or "not true" in user_input.lower():
        contradictions.append("User may be correcting prior context; verify continuity.")

    return {
        "short_term": short_term,
        "episodic": episodic,
        "semantic": semantic_retrieval,
        "continuity_flags": contradictions,
    }


def build_narrative_plan(canonical_state: dict, user_input: str, interaction_mode: str) -> dict:
    rel = canonical_state["mutable"]["relationship_score"]
    unresolved_threads = canonical_state["mutable"]["unresolved_threads"]
    lowered = user_input.lower()
    query_tokens = _tokenize(user_input)

    if "?" in user_input:
        objective = "Answer the user while advancing the current scene."
    elif any(word in lowered for word in ("continue", "next", "then", "after")):
        objective = "Advance the scene with clear next actions."
    else:
        objective = "Stay in character and progress narrative momentum."

    should_use_unresolved = False
    if unresolved_threads:
        latest_thread = unresolved_threads[-1]
        thread_tokens = _tokenize(latest_thread)
        explicit_progression_cue = any(word in lowered for word in ("continue", "next", "then", "after", "what now", "go on"))
        topical_overlap = bool(query_tokens & thread_tokens)
        should_use_unresolved = explicit_progression_cue or topical_overlap

    if unresolved_threads and should_use_unresolved:
        next_beat = f"Address unresolved thread only if it helps answer the user's latest message: {unresolved_threads[-1]}"
    else:
        next_beat = "Directly answer the user's latest message, then add one concrete progression beat tied to the current scene."

    if rel < -30:
        tension = "Interpersonal friction and guarded tone."
    elif rel > 40:
        tension = "Emotional intimacy with a new shared objective."
    else:
        tension = "Light uncertainty to maintain forward narrative pull."

    if interaction_mode != "rp":
        next_beat = "Keep progression concise and conversational."

    return {
        "turn_objective": objective,
        "next_beat": next_beat,
        "tension_element": tension,
        "desired_emotional_shift": "slightly warmer" if rel >= 0 else "cautiously improving",
        "continuity_obligations": [
            f"Respect scene: {canonical_state['mutable']['current_scene']}",
            "Remain in-character and avoid assistant meta-disclaimers.",
        ],
    }


def render_pipeline_context(canonical_state: dict, memory_stack: dict | None, narrative_plan: dict | None) -> str:
    blocks = ["[NARRATIVE PIPELINE CONTEXT]"]
    latest_user_intent = canonical_state.get("mutable", {}).get("last_user_intent", "")
    blocks.append(f'PRIORITY: Respond to the latest user message first: "{latest_user_intent}"')
    blocks.append("Memory snippets are references for continuity only; do not answer old messages unless the user explicitly asks.")

    blocks.append("[CANONICAL STATE]")
    blocks.append(json.dumps(canonical_state, ensure_ascii=False, indent=2))

    if memory_stack is not None:
        compact_memory = {
            "continuity_flags": memory_stack.get("continuity_flags", []),
            "episodic": memory_stack.get("episodic", [])[-4:],
            "semantic": memory_stack.get("semantic", [])[:4],
        }
        blocks.append("[MEMORY STACK]")
        blocks.append(json.dumps(compact_memory, ensure_ascii=False, indent=2))

    if narrative_plan is not None:
        blocks.append("[TURN PLAN]")
        blocks.append(json.dumps(narrative_plan, ensure_ascii=False, indent=2))

    blocks.append("Follow the plan while preserving character voice and concrete story progression.")
    return "\n".join(blocks)


def score_candidate(candidate: str, canonical_state: dict, narrative_plan: dict | None, interaction_mode: str) -> dict:
    text = candidate or ""
    lowered = text.lower()
    persona_tokens = _tokenize(
        " ".join(
            [
                canonical_state["immutable"].get("personality_type", ""),
                canonical_state["immutable"].get("backstory", ""),
                " ".join(canonical_state["immutable"].get("mannerisms", [])),
            ]
        )
    )
    objective_tokens = _tokenize((narrative_plan or {}).get("turn_objective", ""))
    beat_tokens = _tokenize((narrative_plan or {}).get("next_beat", ""))

    in_character = min(10, 3 + _score_overlap(text, persona_tokens))
    progression = min(10, 2 + _score_overlap(text, objective_tokens | beat_tokens))
    if len(text) > 120:
        progression += 1
    if re.search(r"\b(then|next|after|suddenly|meanwhile|decide|plan)\b", lowered):
        progression += 1
    progression = min(10, progression)

    continuity = 10
    if "as an ai" in lowered or "language model" in lowered:
        continuity -= 6
    if interaction_mode == "rp" and not re.search(r'["“].+?["”]', text):
        continuity -= 2
    continuity = max(0, continuity)

    style = 6
    if interaction_mode == "rp" and re.search(r"\*[^*]+\*", text):
        style += 2
    if re.search(r'["“].+?["”]', text):
        style += 1
    style = min(10, style)

    total = in_character * 0.35 + progression * 0.35 + continuity * 0.2 + style * 0.1
    return {
        "total": round(total, 4),
        "in_character": in_character,
        "narrative_progression": progression,
        "continuity": continuity,
        "style": style,
    }


def rank_candidates(candidates: list[str], canonical_state: dict, narrative_plan: dict | None, interaction_mode: str) -> list[dict]:
    ranked = []
    for index, candidate in enumerate(candidates):
        metrics = score_candidate(candidate, canonical_state, narrative_plan, interaction_mode)
        ranked.append({"index": index, "text": candidate, "metrics": metrics})
    ranked.sort(key=lambda row: row["metrics"]["total"], reverse=True)
    return ranked


def needs_critic_pass(text: str, interaction_mode: str) -> bool:
    lowered = (text or "").lower()
    if "as an ai" in lowered or "language model" in lowered:
        return True
    if len((text or "").strip()) < 20:
        return True
    if interaction_mode == "rp":
        has_dialogue = bool(re.search(r'["“].+?["”]', text or ""))
        has_action = bool(re.search(r"\*[^*]+\*", text or ""))
        if not (has_dialogue or has_action):
            return True
    return False


def update_narrative_state(previous_state: dict | None, user_input: str, assistant_reply: str, sentiment_score: int, current_scene: str) -> dict:
    state = dict(previous_state or {})
    unresolved = list(state.get("unresolved_threads", []))
    for match in re.finditer(r"\b(?:will|plan|promise|later|next)\b[^.?!]{0,80}", assistant_reply, flags=re.IGNORECASE):
        snippet = match.group(0).strip()
        if snippet and snippet not in unresolved:
            unresolved.append(snippet)

    state["unresolved_threads"] = unresolved[-8:]
    if sentiment_score > 0:
        shift = "warmer"
    elif sentiment_score < 0:
        shift = "tenser"
    else:
        shift = "steady"

    state["last_emotional_shift"] = shift
    state["last_user_intent"] = user_input[:180]
    state["current_scene"] = current_scene
    if unresolved:
        state["current_goal"] = f"Progress unresolved thread: {unresolved[-1]}"
    else:
        state["current_goal"] = "Maintain character consistency while advancing the scene."
    return state


def append_turn_telemetry(history_profile_name: str, payload: dict) -> None:
    if not get_setting("overhaul_instrumentation_enabled", False):
        return
    safe_name = sanitize_profile_name(history_profile_name)
    if not safe_name:
        safe_name = "session"
    out_dir = "telemetry"
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    out_path = os.path.join(out_dir, f"{safe_name}_telemetry.jsonl")
    row = {"timestamp": datetime.now().isoformat(), **payload}
    with open(out_path, "a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")
