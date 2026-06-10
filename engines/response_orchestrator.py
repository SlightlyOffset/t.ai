import time
from engines.config import get_setting
from engines.formatting import get_tts_split_points
from engines.responses import get_respond_stream
from engines.tts_module import clean_text_for_tts
from engines.hooks import execute_hooks, execute_pipeline


def _resolve_tts_runtime(character_profile: dict) -> dict:
    return {
        "char_voice": character_profile.get("preferred_edge_voice"),
        "char_engine": character_profile.get("tts_engine", "edge-tts"),
        "char_clone_ref": character_profile.get("voice_clone_ref"),
        "char_language": character_profile.get("tts_language", "en"),
        "speak_enable": get_setting("character_speak", False),
        "narrator_voice": get_setting("narration_tts_voice", "en-US-AndrewNeural"),
        "narrator_engine": "edge-tts",
        "narration_enable": get_setting("speak_narration", False),
    }


def _should_enqueue_segment(
    voice: str | None,
    char_voice: str | None,
    narrator_voice: str,
    speak_enable: bool,
    narration_enable: bool,
) -> bool:
    if not speak_enable and narration_enable and voice == narrator_voice:
        return True
    if speak_enable and not narration_enable and voice == char_voice:
        return True
    return speak_enable and narration_enable


def iterate_response_events(
    message: str,
    character_profile: dict,
    history_profile_name: str,
    is_regeneration: bool = False,
    user_name: str = "User",
    post_process_callback = None,
):
    """
    Yield response streaming events decoupled from UI concerns.
    Event shapes:
    - {"type":"chunk","full_response": str}
    - {"type":"tts","payload": tuple[text, voice, engine, clone_ref, language]}
    - {"type":"complete","full_response": str}
    """
    runtime = _resolve_tts_runtime(character_profile)
    target_text = ""
    displayed_text = ""
    current_buffer = ""
    tts_in_narration = False
    smooth_streaming = get_setting("smooth_streaming", True)

    stream_active = True
    stream_iterator = get_respond_stream(
        message,
        character_profile,
        history_profile_name=history_profile_name,
        is_regeneration=is_regeneration,
        user_name=user_name,
        post_process_callback=post_process_callback,
    )

    while True:
        chunk = None
        if stream_active:
            try:
                chunk = next(stream_iterator)
                target_text += chunk
                current_buffer += chunk
                execute_hooks("on_llm_chunk", {"chunk": chunk, "full_response": target_text})

                # Preserve legacy behavior: the TTS master toggle should apply immediately
                # even while a response is still streaming.
                if get_setting("tts_enabled", False):
                    split_points = get_tts_split_points(current_buffer)
                    if split_points:
                        last_point = 0
                        for point in split_points:
                            segment = current_buffer[last_point:point]
                            voice = runtime["narrator_voice"] if tts_in_narration else runtime["char_voice"]
                            engine = runtime["narrator_engine"] if tts_in_narration else runtime["char_engine"]
                            clone_ref = None if tts_in_narration else runtime["char_clone_ref"]
                            language = "en" if tts_in_narration else runtime["char_language"]

                            if "*" in segment:
                                tts_in_narration = not tts_in_narration

                            cleaned = clean_text_for_tts(segment, speak_narration=True)
                            if cleaned and _should_enqueue_segment(
                                voice=voice,
                                char_voice=runtime["char_voice"],
                                narrator_voice=runtime["narrator_voice"],
                                speak_enable=runtime["speak_enable"],
                                narration_enable=runtime["narration_enable"],
                            ):
                                yield {"type": "tts", "payload": (cleaned, voice, engine, clone_ref, language, user_name)}
                            last_point = point
                        current_buffer = current_buffer[last_point:]
            except StopIteration:
                stream_active = False

        if smooth_streaming:
            # Typewriter catch-up loop / step
            while True:
                gap = len(target_text) - len(displayed_text)
                if gap <= 0:
                    break

                # Dynamic step sizing for catching up quickly
                if gap > 30:
                    step_size = gap // 3
                elif gap > 15:
                    step_size = 4
                elif gap > 5:
                    step_size = 2
                else:
                    step_size = 1

                displayed_text += target_text[len(displayed_text):len(displayed_text) + step_size]
                yield {"type": "chunk", "full_response": displayed_text}
                time.sleep(0.03)

                # If LLM is still generating, yield control back to fetch new chunks
                # as long as we're not lagging too far behind (gap < 15)
                if stream_active and (len(target_text) - len(displayed_text)) < 15:
                    break
        else:
            displayed_text = target_text
            if chunk is not None:
                yield {"type": "chunk", "full_response": target_text}

        # Exit when generator is empty and all characters have been typewriter-printed
        if not stream_active and len(displayed_text) == len(target_text):
            break

    if get_setting("tts_enabled", False) and current_buffer.strip():
        cleaned = clean_text_for_tts(current_buffer.strip(), speak_narration=True)
        voice = runtime["narrator_voice"] if tts_in_narration else runtime["char_voice"]
        engine = runtime["narrator_engine"] if tts_in_narration else runtime["char_engine"]
        clone_ref = None if tts_in_narration else runtime["char_clone_ref"]
        language = "en" if tts_in_narration else runtime["char_language"]

        if cleaned and _should_enqueue_segment(
            voice=voice,
            char_voice=runtime["char_voice"],
            narrator_voice=runtime["narrator_voice"],
            speak_enable=runtime["speak_enable"],
            narration_enable=runtime["narration_enable"],
        ):
            yield {"type": "tts", "payload": (cleaned, voice, engine, clone_ref, language, user_name)}

    target_text = execute_pipeline("after_llm_generation", target_text, {
        "character_profile": character_profile,
        "history_profile_name": history_profile_name,
        "is_regeneration": is_regeneration,
    })
    yield {"type": "complete", "full_response": target_text}


