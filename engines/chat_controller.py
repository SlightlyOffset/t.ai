from engines.app_commands import app_commands, RegenerateRequested, RestartRequested, RewindRequested, CompressRequested
from engines.memory_v2 import memory_manager


def get_user_message_number(message: str, history_profile_name: str) -> int | None:
    """Compute the display/history number for a user message."""
    if message.startswith("//"):
        return None
    return memory_manager.get_history_length(history_profile_name) + 1


def get_latest_regeneration_prompt(history_profile_name: str) -> str | None:
    """Return the most recent user message text that can drive a regeneration."""
    pending = memory_manager.get_pending_user_message(history_profile_name)
    if pending:
        return pending
    full_history = memory_manager.load_history(history_profile_name)
    if len(full_history) >= 2 and full_history[-2].get("role") == "user":
        return full_history[-2].get("content", "")
    return None


def handle_command_input(message: str, history_profile_name: str) -> dict | None:
    """
    Handle command-mode input and return an action payload for the UI layer.
    Returns None when input is not a command.
    """
    if not message.startswith("//"):
        return None

    try:
        success, messages = app_commands(message, suppress_output=True)
        if success:
            return {"type": "command_success", "messages": messages}
    except RestartRequested:
        raise
    except RegenerateRequested:
        return {"type": "regenerate", "user_text": get_latest_regeneration_prompt(history_profile_name)}
    except CompressRequested:
        return {"type": "compress"}
    except RewindRequested as rewind_request:
        original_count, kept_count = memory_manager.rewind_history(
            history_profile_name,
            rewind_request.message_number,
        )
        return {
            "type": "rewind",
            "original_count": original_count,
            "kept_count": kept_count,
        }

    return {"type": "command_noop", "messages": []}


def previous_response_variant(history_profile_name: str) -> dict | None:
    """Move to the previous assistant alternative and persist selection."""
    full_history = memory_manager.load_history(history_profile_name)
    if not full_history or full_history[-1].get("role") != "assistant":
        return None

    last_msg = full_history[-1]
    alternatives = last_msg.get("alternatives", [])
    selected_index = last_msg.get("selected_index", 0)
    if not alternatives or selected_index <= 0:
        return None

    new_index = selected_index - 1
    last_msg["selected_index"] = new_index
    last_msg["content"] = alternatives[new_index]
    memory_manager.save_history(history_profile_name, full_history)
    return {"content": last_msg["content"], "index": new_index, "total": len(alternatives)}


def next_response_variant_or_regen(history_profile_name: str) -> dict | None:
    """Advance assistant alternative or return regeneration prompt info."""
    full_history = memory_manager.load_history(history_profile_name)
    if not full_history or full_history[-1].get("role") != "assistant":
        return None

    last_msg = full_history[-1]
    alternatives = last_msg.get("alternatives", [])
    selected_index = last_msg.get("selected_index", 0)
    if alternatives and selected_index < len(alternatives) - 1:
        new_index = selected_index + 1
        last_msg["selected_index"] = new_index
        last_msg["content"] = alternatives[new_index]
        memory_manager.save_history(history_profile_name, full_history)
        return {"type": "next", "content": last_msg["content"], "index": new_index, "total": len(alternatives)}

    return {"type": "regenerate", "user_text": get_latest_regeneration_prompt(history_profile_name)}
