"""
Main menu and TUI components for the AI Desktop Companion.
"""
# Standard library imports
import json
import os
import queue
import random
import threading
import time
import sys

# Third-party imports
import ollama
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static, Label, Select, ProgressBar, Switch, TextArea
from textual_image.widget import Image
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual import work, events
from textual.reactive import reactive
from textual.message import Message

# First-party imports
from engines.app_commands import RestartRequested
from engines.chat_controller import (
    get_user_message_number,
    handle_command_input,
    next_response_variant_or_regen,
    previous_response_variant,
)
from engines.config import update_setting, get_setting
from engines.formatting import format_roleplay_text, format_summary_text
from engines.profile_state import (
    build_sidebar_state,
    get_initial_avatar_paths,
    load_profile_session,
    resolve_selected_paths,
)
from engines.recap_service import (
    generate_recap_summary,
    generate_updated_memory_core,
    rolling_summary_target_index,
    split_recap_history,
)
from engines.response_orchestrator import iterate_response_events
from engines.tts_module import generate_audio, play_audio
from engines.memory_v2 import memory_manager

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def set_terminal_appearance(title: str = None):
    """
    Sets the tab title in Windows Terminal.
    """
    # Handle Title (Standard ANSI)
    if title:
        sys.stdout.write(f"\033]0;{title}\007")

    sys.stdout.flush()


def format_rp(text: str) -> str:
    """Legacy compatibility helper used by older tests/imports."""
    if not text:
        return ""
    parts = text.split("*")
    for index in range(1, len(parts), 2):
        parts[index] = f"[i][dim]{parts[index]}[/dim][/i]"
    return "".join(parts)


def pick_profile():
    """Legacy compatibility shim for older tests/tools."""
    return None


def pick_user_profile():
    """Legacy compatibility shim for older tests/tools."""
    return None


class ChatInput(TextArea):
    """A multi-line input field that grows vertically up to a limit."""
    class Submitted(Message):
        """Sent when the user presses Enter (without Shift)."""
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def on_mount(self) -> None:
        self.show_line_numbers = False
        # Height 3 allows for 1 line of text + top/bottom borders
        self.height = 3
        self.focus()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Resize height based on content, accounting for borders."""
        line_count = len(self.document.lines)
        # text lines + 2 for the borders, maxing out at 10 total height
        self.height = min(max(1, line_count), 8) + 2

    def on_key(self, event: events.Key) -> None:
        """Handle Enter for submission and provide fallbacks for newlines."""
        if event.key == "enter":
            # Only submit on plain "enter".
            # If the terminal sends "shift+enter" or "ctrl+enter" as distinct keys,
            # they will fall through to the default TextArea behavior (newline).
            event.prevent_default()
            text = self.text.strip()
            if text:
                self.post_message(self.Submitted(text))
                self.text = ""
                self.height = 3
        elif event.key == "ctrl+j":
            # Fallback: Many terminals send Ctrl+J for newline or can be used
            # as a dedicated "Force Newline" shortcut.
            self.insert("\n")
            event.prevent_default()

class TaiMenu(App):
    """t.ai - Logic-focused TUI implementation."""
    TITLE = "t.ai (made with love from a lone developer! 💖)"

    BINDINGS = [
        ("ctrl+b", "toggle_sidebar", "Toggle Sidebar"),
        ("ctrl+o", "open_profile_select", "Profiles"),
        ("ctrl+q", "quit", "Quit"),
        ("alt+left", "previous_response", "Prev Resp"),
        ("alt+right", "next_or_regenerate_response", "Next/Regen"),
    ]

    show_sidebar = reactive(True)

    CSS_PATH = "tcss/menu.tcss"

    TTS_ENGINES = [
        ("Edge TTS", "edge-tts"),
        ("XTTS-V2", "xtts")
    ]

    EDGE_VOICES = [
        ("Andrew (Male)", "en-US-AndrewNeural"),
        ("Emma (Female)", "en-US-EmmaNeural"),
        ("Brian (Male)", "en-GB-BrianNeural"),
        ("Sonia (Female)", "en-GB-SoniaNeural"),
        ("Aria (Female)", "en-US-AriaNeural"),
        ("Guy (Male)", "en-US-GuyNeural"),
        ("Ava (Female)", "en-US-AvaNeural"),
        ("AvaMultilingual (Female)", "en-US-AvaMultilingualNeural")
    ]

    # Global TTS queue
    tts_text_queue = queue.Queue()
    audio_file_queue = queue.Queue()

    def __init__(self, char_path, user_path, **kwargs):
        super().__init__(**kwargs)
        self.char_path, self.user_path = resolve_selected_paths(char_path, user_path)

        self.character_profile = None
        self.char_name_lbl_color = "magenta"
        self.user_profile = None
        self.ch_name = "Assistant"
        self.user_name = "User"
        self.user_name_lbl_color = "cyan"
        self.history_profile_name = ""
        self._current_char_avatar_path = None
        self._current_user_avatar_path = None

    def watch_show_sidebar(self, show: bool) -> None:
        """Called when show_sidebar reactive property changes."""
        try:
            self.query_one("#status_sidebar").display = show
        except Exception:
            pass # Widget is not mounted yet

    def action_toggle_sidebar(self) -> None:
        """Toggle the status sidebar visibility."""
        self.show_sidebar = not self.show_sidebar

    def action_previous_response(self) -> None:
        """Scrolls back to the previous AI response for the current prompt."""
        result = previous_response_variant(self.history_profile_name)
        if result:
            self.refresh_last_ai_message(result["content"], result["index"], result["total"])

    def action_next_or_regenerate_response(self) -> None:
        """Scrolls forward to the next response, or regenerates if at the end."""
        result = next_response_variant_or_regen(self.history_profile_name)
        if not result:
            return

        if result["type"] == "next":
            self.refresh_last_ai_message(result["content"], result["index"], result["total"])
            return

        user_text = result.get("user_text")
        if user_text:
            try:
                ai_bubble = self.query(".ai_bubble").last()
                ai_bubble.update(
                    f"{self._message_header('assistant', self._current_assistant_message_number())}\n"
                    "[dim italic]Regenerating response...[/dim italic]"
                )
            except Exception:
                pass
            self.stream_response(user_text, is_regeneration=True)

    def _message_header(self, role: str, message_number: int | None) -> str:
        """Build a standardized bubble header with optional message numbering."""
        if role == "user":
            name = self.user_name
            color = self.user_name_lbl_color
        else:
            name = self.ch_name
            color = self.char_name_lbl_color

        if message_number is None:
            return f"[bold {color}]{name}:[/bold {color}]"
        return f"[dim]#{message_number}[/dim] [bold {color}]{name}:[/bold {color}]"

    def _current_assistant_message_number(self) -> int | None:
        """Return the 1-based history index for the latest assistant message, if available."""
        full_history = memory_manager.load_history(self.history_profile_name)
        if full_history and full_history[-1].get("role") == "assistant":
            return len(full_history)
        return None

    def refresh_last_ai_message(self, content: str, index: int, total: int) -> None:
        """Updates the text and indicator of the last AI message in the UI."""
        try:
            ai_bubble = self.query(".ai_bubble").last()
            indicator = f"\n\n[dim]< {index + 1}/{total} >[/dim]" if total > 1 else ""
            formatted_text = self.format_rp(content, role="assistant") + indicator
            ai_bubble.update(
                f"{self._message_header('assistant', self._current_assistant_message_number())}\n{formatted_text}"
            )
        except Exception:
            pass

    def action_open_profile_select(self) -> None:
        """Open the profile selection screen."""
        from ProfileSelectScreen import ProfileSelect
        self.push_screen(ProfileSelect(), callback=self.on_profile_selected)

    def compose(self) -> ComposeResult:
        self._current_char_avatar_path, self._current_user_avatar_path = get_initial_avatar_paths(
            self.char_path,
            self.user_path,
        )

        yield Header(show_clock=True)
        with Horizontal(id="app_body"):
            with Vertical(id="chat_container"):
                with ScrollableContainer(id="chat_list"):
                    yield Label("[bold green]System:[/bold green] Waiting for profile...", id="init_msg", classes="system_msg")
                yield ChatInput(id="user_input")
            with Vertical(id="status_sidebar"):
                yield Label("--- Character ---", classes="sidebar_header")
                with Vertical(id="char_avatar_wrap", classes="avatar_container"):
                    yield Image(self._current_char_avatar_path, id="avatar_portrait_character")
                yield Label("Name: [bold magenta]None[/bold magenta]", id="lbl_char")
                yield Label("Mood: [bold]Neutral[/bold]", id="lbl_mood")
                yield Label("Relationship:", classes="sidebar_label")
                yield ProgressBar(total=200, show_percentage=False, id="rel_bar")
                yield Label("Score: [bold]0[/bold]", id="lbl_rel")

                yield Label("--- User ---", classes="sidebar_header")
                with Vertical(id="user_avatar_wrap", classes="avatar_container"):
                    yield Image(self._current_user_avatar_path, id="avatar_portrait_user")
                yield Label("User: [bold cyan]None[/bold cyan]", id="lbl_user")

                yield Label("--- Settings ---", classes="sidebar_header")
                yield Label("LLM Model:", classes="sidebar_label")
                yield Select([], id="model_select", prompt="Select Model")

                yield Label("TTS Engine:", classes="sidebar_label")
                yield Select([], id="tts_engine_select", prompt="Select TTS Engine")

                with Horizontal(classes="setting_row"):
                    yield Label("TTS Master:", classes="setting_label")
                    yield Switch(value=get_setting("tts_enabled", False), id="sw_tts")

                with Horizontal(classes="setting_row"):
                    yield Label("Dialogue:", classes="setting_label")
                    yield Switch(value=get_setting("character_speak", False), id="sw_dialogue")

                with Horizontal(classes="setting_row"):
                    yield Label("Narration:", classes="setting_label")
                    yield Switch(value=get_setting("speak_narration", False), id="sw_narration")

                yield Label("Companion Voice(for edge TTS):", classes="sidebar_label")
                yield Select([], id="character_voice_select", prompt="Select Character Voice")
                yield Label("Narration Voice(for edge TTS):", classes="sidebar_label")
                yield Select([], id="narration_voice_select", prompt="Select Narration Voice")

        yield Footer()

    def on_mount(self) -> None:
        """Initializes the app and load character profiles."""
        self.start_tts_worker()
        self.load_initial_state()

        if not self.char_path:
            from ProfileSelectScreen import ProfileSelect
            self.push_screen(ProfileSelect(), callback=self.on_profile_selected)
            return

        self.populate_models()
        self.populate_voices()
        self.populate_tts_engines()

    def on_profile_selected(self, result: dict) -> None:
        """Callback handled when ProfileSelect screen is dismissed."""
        if result:
            char_name = result.get("character")
            user_name = result.get("user")

            char_path = os.path.join("profiles", char_name) if char_name else None
            user_path = os.path.join("user_profiles", user_name) if user_name else None

            self.switch_profile(char_path, user_path)

    def switch_profile(self, char_path: str, user_path: str = None) -> None:
        """Resets the app state and loads a new profile."""
        if not char_path:
            return

        # Clear TTS queues
        while not self.tts_text_queue.empty():
            try:
                self.tts_text_queue.get_nowait()
                self.tts_text_queue.task_done()
            except queue.Empty:
                break
        while not self.audio_file_queue.empty():
            try:
                self.audio_file_queue.get_nowait()
                self.audio_file_queue.task_done()
            except queue.Empty:
                break

        self.char_path = char_path
        self.user_path = user_path

        # Re-initialize state
        self.load_initial_state()
        self.populate_models()
        self.populate_voices()
        self.populate_tts_engines()

    @staticmethod
    def format_summary(summary: str) -> str:
        return format_summary_text(summary)

    def format_rp(self, text, role) -> str:
        """
        Formats text with basic markdown-like syntax for the TUI.
        - **bold** -> [b]bold[/b]
        - *italic* -> [i][dim]italic[/dim][/i] (Narration)
        - "speech" -> [yellow]"speech"[/yellow] (Highlight)
        """
        character_profile = self.character_profile or {}
        user_name = self.user_profile.get("name", "User") if self.user_profile else "User"
        character_name = character_profile.get("name", "Assistant")
        user_speech_color = "yellow"
        if self.user_profile:
            user_speech_color = self.user_profile.get("colors", {}).get("speech_highlight", "yellow")
        assistant_speech_color = character_profile.get("colors", {}).get("speech_highlight", "yellow")
        return format_roleplay_text(
            text=text,
            role=role,
            user_name=user_name,
            character_name=character_name,
            user_speech_color=user_speech_color,
            assistant_speech_color=assistant_speech_color,
        )

    def populate_tts_engines(self) -> None:
        """Populate the TTS engine selection list with available engines."""
        select = self.query_one("#tts_engine_select", Select)
        select.set_options(self.TTS_ENGINES)
        current_engine = self.character_profile.get("tts_engine", get_setting("default_tts_engine", "edge-tts"))
        for label, value in self.TTS_ENGINES:
            if value == current_engine:
                select.value = value
                break

    def populate_models(self) -> None:
        """Fetch available models from Ollama and populate the Select widget."""
        try:
            raw_models = ollama.list().models
            options = []
            for m in raw_models:
                full_name = m.model
                # Display only the part after the last slash (removes user/repo paths)
                display_name = full_name.split('/')[-1]
                options.append((display_name, full_name))

            select = self.query_one("#model_select", Select)
            select.set_options(options)

            # Set current model as default
            current_model = self.character_profile.get("llm_model", get_setting("default_llm_model", "llama3"))
            # Find the best match in the list
            for label, value in options:
                if value == current_model or value.startswith(current_model + ":"):
                    select.value = value
                    break
        except Exception:
            pass

    def populate_voices(self) -> None:
        """Populate the narration voice selection list with Edge-TTS options."""
        select_na = self.query_one("#narration_voice_select", Select)
        select_na.set_options(self.EDGE_VOICES)
        current_na_voice = get_setting("narration_tts_voice", "en-US-AndrewNeural")
        select_na.value = current_na_voice

        select_ch = self.query_one("#character_voice_select", Select)
        select_ch.set_options(self.EDGE_VOICES)
        current_ch_voice = self.character_profile.get("preferred_edge_voice", get_setting("narration_tts_voice", "en-US-AndrewNeural"))
        select_ch.value = current_ch_voice

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle toggle switches for TTS settings."""
        if event.switch.id == "sw_tts":
            update_setting("tts_enabled", event.value)
            self.add_message(f"TTS Master: {'[bold green]ON[/bold green]' if event.value else '[bold red]OFF[/bold red]'}", role="system")
        elif event.switch.id == "sw_dialogue":
            update_setting("character_speak", event.value)
            self.add_message(f"Dialogue: {'[bold green]ON[/bold green]' if event.value else '[bold red]OFF[/bold red]'}", role="system")
        elif event.switch.id == "sw_narration":
            update_setting("speak_narration", event.value)
            self.add_message(f"Narration: {'[bold green]ON[/bold green]' if event.value else '[bold red]OFF[/bold red]'}", role="system")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Update the character profile with selected LLM, Character Voice, or Narration Voice."""
        from engines.utilities import save_json_atomic

        # Handle cases where value might be Select.BLANK (NULL)
        val = event.value if event.value != Select.BLANK else None

        if event.select.id == "model_select" and val is not None:
            self.character_profile["llm_model"] = val
            save_json_atomic(self.char_path, self.character_profile)
            self.add_message(f"LLM model switched to [bold]{val}[/bold]", role="system")
        elif event.select.id == "character_voice_select" and val is not None:
            self.character_profile["preferred_edge_voice"] = val
            save_json_atomic(self.char_path, self.character_profile)
            self.add_message(f"Companion voice set to [bold]{val}[/bold]", role="system")
        elif event.select.id == "narration_voice_select" and val is not None:
            if update_setting("narration_tts_voice", val):
                self.add_message(f"Narration voice set to [bold]{val}[/bold]", role="system")
            else:
                self.add_message(f"Failed to set narration voice to [bold]{val}[/bold]", role="system")
        elif event.select.id == "tts_engine_select" and val is not None:
            self.character_profile["tts_engine"] = val
            save_json_atomic(self.char_path, self.character_profile)
            self.add_message(f"TTS engine switched to [bold]{val}[/bold]", role="system")

    def start_tts_worker(self) -> None:
        """Starts a worker thread for TTS generation and playback."""
        threading.Thread(target=self.tts_generation_worker, daemon=True).start()
        threading.Thread(target=self.tts_playback_worker, daemon=True).start()

    def tts_generation_worker(self) -> None:
        """Worker thread for generating TTS audio files."""
        while True:
            data = self.tts_text_queue.get()
            if data is None: break
            text, voice, engine, clone_ref, language = data
            temp_filename = os.path.join(os.environ.get("TEMP", "/tmp"), f"tts_{time.time()}.mp3")
            if generate_audio(text, temp_filename, voice=voice, engine=engine, clone_ref=clone_ref, language=language):
                self.audio_file_queue.put(temp_filename)
            self.tts_text_queue.task_done()

    def tts_playback_worker(self) -> None:
        """Worker thread for playing TTS audio files."""
        while True:
            filename = self.audio_file_queue.get()
            if filename is None: break
            play_audio(filename)
            self.audio_file_queue.task_done()

    def print_starter_message(self) -> None:
        """Prints starter messages to the chat list."""
        starter_messages = self.character_profile.get("starter_messages", [])
        if starter_messages:
            random.shuffle(starter_messages)
            self.add_message(self.format_rp(starter_messages[0], role="assistant"), role="assistant", message_number=1)
            memory_manager.save_history(self.history_profile_name, [{"role": "assistant",
                                                                     "content": starter_messages[0]}],
                                        mood_score=self.character_profile.get("relationship_score", 0))

    def run_recap(self):
        messages_history = memory_manager.load_history(self.history_profile_name)
        if not messages_history:
            return

        recap_state = split_recap_history(messages_history)
        if recap_state["mode"] == "full":
            self.add_message(f"--- Recap: {len(messages_history)} messages loaded ---", role="system")
            for index, msg_data in enumerate(recap_state["messages"], start=1):
                role = msg_data.get("role", "assistant")
                content = msg_data.get("content", "")
                if role != "system":
                    content = self.format_rp(content, role=role)
                message_number = index if role in ("user", "assistant") else None
                self.add_message(content, role=role, msg_data=msg_data, message_number=message_number)
            self.add_message("--- Recap complete ---", role="system")
        else:
            self.add_message("--- [bold cyan]Analyzing past memories...[/bold cyan] ---", role="system")
            self.summarize_and_display(
                recap_state["older_history"],
                recap_state["recent_history"],
                recap_state["recent_start_index"],
            )

    @work(thread=True)
    def summarize_and_display(self, older_history: list, recent_history: list, recent_start_index: int):
        """Worker for summarizing history in the background."""
        summary = generate_recap_summary(older_history, user_name=self.user_name, char_name=self.ch_name)

        def update_ui():
            self.add_message(self.format_summary(summary), role="summary")
            self.add_message("--- Recent Continuity ---", role="system")
            for offset, msg_data in enumerate(recent_history):
                role = msg_data.get("role", "assistant")
                content = msg_data.get("content", "")
                if role != "system":
                    content = self.format_rp(content, role=role)
                message_number = recent_start_index + offset if role in ("user", "assistant") else None
                self.add_message(content, role=role, msg_data=msg_data, message_number=message_number)
            self.add_message("--- Recap complete ---", role="system")

        self.app.call_from_thread(update_ui)

    def load_initial_state(self) -> None:
        """Loads profiles and settings based on pre-selected paths or settings.json."""
        self.char_path, self.user_path = resolve_selected_paths(self.char_path, self.user_path)

        if not self.char_path:
            # Still no character path? We'll handle this in the next task by pushing ProfileSelectScreen
            # For now, we must not exit if we want the TUI to stay alive and show the selection screen later.
            return

        # Clear existing chat if any (for profile switching)
        try:
            chat_list = self.query_one("#chat_list")
            # We can't just clear(), we need to remove children
            for child in chat_list.children:
                child.remove()
        except Exception:
            pass # App might not be fully mounted yet

        session_state = load_profile_session(self.char_path, self.user_path)
        self.character_profile = session_state["character_profile"]
        self.user_profile = session_state["user_profile"]
        self.ch_name = session_state["ch_name"]
        self.user_name = session_state["user_name"]
        self.char_name_lbl_color = session_state["char_name_lbl_color"]
        self.user_name_lbl_color = session_state["user_name_lbl_color"]
        self.history_profile_name = session_state["history_profile_name"]
        update_setting("current_character_profile", os.path.basename(self.char_path))

        if self.user_path:
            update_setting("current_user_profile", os.path.basename(self.user_path))
        else:
            self.user_name = "User"

        self.update_sidebar()
        self.add_message(f"Loaded character profile: [bold]{self.ch_name}[/bold]", role="system")

        # Print character's starter messages and save to memory (if any, which should always be any)
        # Only do this if the history doesn't exist yet, to avoid repeating starter messages on every launch
        has_history = memory_manager.has_history(self.history_profile_name)
        if not has_history:
            self.print_starter_message()

        # Run a history recap on startup only when enabled and prior history exists.
        if get_setting("auto_recap_on_start", False) and has_history:
            self.run_recap()


        # Print tip message
        self.add_message("Tip: Use [bold]Ctrl+B[/bold] to toggle the sidebar.", role="tip_message")
        self.add_message("Tip: Use [bold]Ctrl+J[/bold] for a newline.", role="tip_message")
        self.add_message("Tip: Type [bold cyan]//help[/bold cyan] for a list of available commands.", role="tip_message")

    def update_sidebar(self):
        """Update the sidebar content including avatars and relationship stats."""
        state = build_sidebar_state(
            character_profile=self.character_profile or {},
            user_profile=self.user_profile,
            ch_name=self.ch_name,
            user_name=self.user_name,
            char_name_lbl_color=self.char_name_lbl_color,
            user_name_lbl_color=self.user_name_lbl_color,
        )

        try:
            if getattr(self, "_current_char_avatar_path", None) != state["char_avatar_abs"]:
                char_img = self.query_one("#avatar_portrait_character", Image)
                char_img.image = state["char_avatar_abs"]
                self._current_char_avatar_path = state["char_avatar_abs"]

            if getattr(self, "_current_user_avatar_path", None) != state["user_avatar_abs"]:
                user_img = self.query_one("#avatar_portrait_user", Image)
                user_img.image = state["user_avatar_abs"]
                self._current_user_avatar_path = state["user_avatar_abs"]
        except Exception:
            pass

        self.query_one("#lbl_char").update(state["char_label"])
        self.query_one("#lbl_mood").update(state["mood_label"])
        self.query_one("#lbl_rel").update(state["rel_label"])
        self.query_one("#lbl_user").update(state["user_label"])
        self.query_one("#rel_bar").progress = state["rel_progress"]

    def add_message(self, text, role="user", msg_data=None, message_number: int | None = None):
        container = self.query_one("#chat_list")
        if role == "system":
            container.mount(Static(text, markup=True, classes="system_msg"))
        elif role == "command":
            container.mount(Static(text, markup=True, classes="command_msg"))
        elif role == "summary":
            container.mount(Static(text, markup=True, classes="summary_msg"))
        elif role == "tip_message":
            container.mount(Static(text, markup=True, classes="tip_msg"))
        else:
            row_class = "user_row" if role == "user" else "ai_row"
            bubble_class = "user_bubble" if role == "user" else "ai_bubble"
            header = self._message_header(role, message_number)

            # Multi-response pagination indicator
            indicator = ""
            if msg_data and role == "assistant":
                alternatives = msg_data.get("alternatives", [])
                if alternatives:
                    idx = msg_data.get("selected_index", 0)
                    indicator = f"\n\n[dim]< {idx + 1}/{len(alternatives)} >[/dim]"

            bubble = Static(f"{header}\n{text}{indicator}", markup=True, classes=f"message {bubble_class}")
            row = Horizontal(bubble, classes=f"message_row {row_class}")

            container.mount(row)

        container.scroll_end(animate=False)

    def reload_chat_from_history(self) -> None:
        """Rebuilds the visible chat list from persisted history."""
        container = self.query_one("#chat_list", ScrollableContainer)
        for child in list(container.children):
            child.remove()

        history = memory_manager.load_history(self.history_profile_name)
        for index, msg_data in enumerate(history, start=1):
            role = msg_data.get("role", "assistant")
            content = msg_data.get("content", "")
            if role != "system":
                content = self.format_rp(content, role=role)
            message_number = index if role in ("user", "assistant") else None
            self.add_message(content, role=role, msg_data=msg_data, message_number=message_number)

    async def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        """Handles user input submission from ChatInput."""
        message = event.value.strip()
        if not message: return

        # Format user message for display
        display_message = self.format_rp(message, role="user")
        user_message_number = get_user_message_number(message, self.history_profile_name)
        self.add_message(display_message, role="user", message_number=user_message_number)

        # Handle commands (original message)
        if message.startswith("//"):
            try:
                command_action = handle_command_input(message, self.history_profile_name)
            except RestartRequested:
                self.exit()
                raise
            except ValueError as exc:
                self.add_message(f"[ERROR] {exc}", role="command")
                return

            if not command_action:
                return

            if command_action["type"] == "command_success":
                for msg in command_action["messages"]:
                    self.add_message(msg, role="command")
                self.update_sidebar()
                return

            if command_action["type"] == "regenerate":
                try:
                    self.query_one("#chat_list").children[-1].remove()
                except Exception:
                    pass
                if command_action.get("user_text"):
                    self.stream_response(command_action["user_text"], is_regeneration=True)
                return

            if command_action["type"] == "rewind":
                self.reload_chat_from_history()
                self.check_for_rolling_summary()
                self.add_message(
                    f"[SYSTEM] Rewound conversation from {command_action['original_count']} to {command_action['kept_count']} messages.",
                    role="command",
                )
                return

            if command_action["type"] == "command_noop":
                self.add_message("[SYSTEM] Recognized command pattern but no action taken: Non-existent command.", role="command")
                return

        # Trigger AI response
        assistant_message_number = (user_message_number + 1) if user_message_number is not None else None
        self.stream_response(message, message_number=assistant_message_number)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Fallback for any standard Input widgets (legacy or other)."""
        # Create a mock event to reuse logic if needed, or just redirect
        class MockEvent:
            def __init__(self, value):
                self.value = value
        await self.on_chat_input_submitted(MockEvent(event.value))

    def _prepare_stream_widgets(
        self,
        is_regeneration: bool,
        message_number: int | None = None,
    ) -> tuple[ScrollableContainer, Static, str]:
        """Resolve chat widgets on the main thread before background streaming starts."""
        container = self.query_one("#chat_list", ScrollableContainer)
        history_len = memory_manager.get_history_length(self.history_profile_name)
        assistant_message_number = message_number
        if assistant_message_number is None:
            assistant_message_number = history_len if is_regeneration else history_len + 2
        header = self._message_header("assistant", assistant_message_number)

        if is_regeneration:
            try:
                ai_msg = self.query(".ai_bubble").last()
            except Exception:
                ai_msg = Static(
                    f"{header}\n",
                    markup=True,
                    classes="message ai_bubble",
                )
                row = Horizontal(ai_msg, classes="message_row ai_row")
                container.mount(row)
        else:
            ai_msg = Static(
                f"{header}\n",
                markup=True,
                classes="message ai_bubble",
            )
            row = Horizontal(ai_msg, classes="message_row ai_row")
            container.mount(row)

        container.scroll_end(animate=False)
        return container, ai_msg, header

    def stream_response(self, message: str, is_regeneration: bool = False, message_number: int | None = None) -> None:
        """Prepare UI targets on the main thread, then stream in a worker thread."""
        container, ai_msg, header = self._prepare_stream_widgets(is_regeneration, message_number=message_number)
        self._stream_response_worker(message, is_regeneration, container, ai_msg, header)

    @work(thread=True)
    def _stream_response_worker(
        self,
        message: str,
        is_regeneration: bool,
        container: ScrollableContainer,
        ai_msg: Static,
        header: str,
    ) -> None:
        """Worker to handle the LLM streaming and TTS queuing."""
        full_response = ""
        for event in iterate_response_events(
            message=message,
            character_profile=self.character_profile,
            history_profile_name=self.history_profile_name,
            is_regeneration=is_regeneration,
        ):
            if event["type"] == "chunk":
                full_response = event["full_response"]
                self.app.call_from_thread(ai_msg.update, f"{header}\n{self.format_rp(full_response, role='assistant')}")
                self.app.call_from_thread(container.scroll_end, animate=False)
            elif event["type"] == "tts":
                self.tts_text_queue.put(event["payload"])
            elif event["type"] == "complete":
                full_response = event["full_response"]

        # Add pagination indicator if alternatives exist
        full_history = memory_manager.load_history(self.history_profile_name)
        if full_history and full_history[-1].get("role") == "assistant":
            last_msg = full_history[-1]
            alternatives = last_msg.get("alternatives", [])
            if alternatives:
                idx = last_msg.get("selected_index", 0)
                indicator = f"\n\n[dim]< {idx + 1}/{len(alternatives)} >[/dim]"
                self.app.call_from_thread(ai_msg.update, f"{header}\n{self.format_rp(full_response, role='assistant')}{indicator}")

        # Refresh score display
        profile_path = os.path.join("profiles", get_setting("current_character_profile"))
        with open(profile_path, "r", encoding="utf-8") as f:
            self.character_profile = json.load(f)
        self.app.call_from_thread(self.update_sidebar)

        # Trigger rolling summarization check
        self.check_for_rolling_summary()

    def check_for_rolling_summary(self):
        """Checks if enough new messages have accumulated to update the Memory Core."""
        history_len = memory_manager.get_history_length(self.history_profile_name)
        last_index = memory_manager.get_last_summarized_index(self.history_profile_name)
        limit = get_setting("memory_limit", 15)
        to_summarize_count = rolling_summary_target_index(history_len, last_index, limit)
        if to_summarize_count is not None:
            full_history = memory_manager.load_history(self.history_profile_name)
            new_messages_to_sum = full_history[last_index:to_summarize_count]
            self.perform_rolling_summary(new_messages_to_sum, to_summarize_count)

    @work(thread=True)
    def perform_rolling_summary(self, new_messages: list, new_index: int):
        """Background worker to update the Memory Core."""
        existing_core = memory_manager.get_memory_core(self.history_profile_name)
        new_core = generate_updated_memory_core(
            existing_core,
            new_messages,
            user_name=self.user_name,
            char_name=self.ch_name,
        )

        # Persist the update
        memory_manager.update_memory_core(self.history_profile_name, new_core, new_index)
        self.log(f"Memory Core updated to index {new_index}")


if __name__ == "__main__":
    app = TaiMenu(char_path=None, user_path=None)
    app.run()
