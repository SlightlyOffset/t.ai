from engines.config import get_setting
from engines.responses import generate_summary, update_rolling_summary


def split_recap_history(messages_history: list, short_history_limit: int = 15, recent_window: int = 5) -> dict:
    """Split history into either direct display mode or summarized mode."""
    if len(messages_history) <= short_history_limit:
        return {"mode": "full", "messages": messages_history}
    older_history = messages_history[:-recent_window]
    recent_history = messages_history[-recent_window:]
    return {
        "mode": "summary",
        "older_history": older_history,
        "recent_history": recent_history,
        "recent_start_index": len(older_history) + 1,
    }


def generate_recap_summary(older_history: list, user_name: str, char_name: str, model: str = None) -> str:
    summarizer_model = model or get_setting("summarizer_model", "gemma2:2b")
    remote_url = get_setting("remote_llm_url")
    return generate_summary(
        older_history,
        model=summarizer_model,
        remote_url=remote_url,
        user_name=user_name,
        char_name=char_name,
    )


def rolling_summary_target_index(history_len: int, last_index: int, memory_limit: int) -> int | None:
    """Compute index up to which history should be summarized, or None if no update needed."""
    if (history_len - last_index) <= (memory_limit + 5):
        return None
    to_summarize_count = history_len - memory_limit
    if to_summarize_count <= last_index:
        return None
    return to_summarize_count


def generate_updated_memory_core(existing_core: str, new_messages: list, user_name: str, char_name: str, model: str = None) -> str:
    summarizer_model = model or get_setting("summarizer_model", "gemma2:2b")
    remote_url = get_setting("remote_llm_url")
    return update_rolling_summary(
        existing_core,
        new_messages,
        model=summarizer_model,
        remote_url=remote_url,
        user_name=user_name,
        char_name=char_name,
    )
