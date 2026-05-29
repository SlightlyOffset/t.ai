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
from textual_image.widget import Image, SixelImage, TGPImage, HalfcellImage
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
from engines.formatting import TextFormatter
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
from engines.lorebook import sync_lore_to_remote, load_lorebook

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        ("ctrl+s", "open_settings", "Settings"),
        ("ctrl+q", "quit", "Quit"),
        ("alt+left", "previous_response", "Prev Resp"),
        ("alt+right", "next_or_regenerate_response", "Next/Regen"),
    ]

    show_sidebar = reactive(True)
    remote_status = reactive("")

    CSS_PATH = "tcss/menu.tcss"

    TTS_ENGINES = [
        ("Edge TTS", "edge-tts"),
        ("XTTS-V2", "xtts")
    ]

    INTERACTION_MODES = [
        ("Roleplay (RP)", "rp"),
        ("Casual", "casual")
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

    IMAGE_PROTOCOLS = [
        ("Auto", "auto"),
        ("Kitty", "kitty"),
        ("Sixel", "sixel"),
        ("Blocky", "blocky"),
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

    def _resolve_image_widget_type(self) -> type[Image]:
        protocol = get_setting("image_protocol", "auto")
        if protocol == "kitty":
            return TGPImage
        if protocol == "sixel":
            return SixelImage
        if protocol == "blocky":
            return HalfcellImage
        return Image

    def _build_avatar_widget(self, image_path: str | None, widget_id: str):
        widget_type = self._resolve_image_widget_type()
        return widget_type(image_path, id=widget_id)

    def _mount_avatar_widget(self, container_id: str, widget_id: str, image_path: str | None) -> None:
        container = self.query_one(f"#{container_id}", Vertical)
        desired_widget_type = self._resolve_image_widget_type()
        try:
            existing = self.query_one(f"#{widget_id}")
        except Exception:
            existing = None

        if existing is not None:
            if isinstance(existing, desired_widget_type):
                existing.image = image_path
                return
            existing.remove()
            self.call_after_refresh(self._mount_avatar_widget, container_id, widget_id, image_path)
            return

        container.mount(self._build_avatar_widget(image_path, widget_id))

    def _set_avatar_image(self, container_id: str, widget_id: str, image_path: str | None) -> None:
        try:
            avatar_widget = self.query_one(f"#{widget_id}")
            avatar_widget.image = image_path
        except Exception:
            self._mount_avatar_widget(container_id, widget_id, image_path)

    def remount_avatar_widgets(self) -> None:
        self._mount_avatar_widget("char_avatar_wrap", "avatar_portrait_character", self._current_char_avatar_path)
        self._mount_avatar_widget("user_avatar_wrap", "avatar_portrait_user", self._current_user_avatar_path)

    def watch_show_sidebar(self, show: bool) -> None:
        """Called when show_sidebar reactive property changes."""
        try:
            self.query_one("#status_sidebar").display = show
        except Exception:
            pass # Widget is not mounted yet

    def watch_remote_status(self, status: str) -> None:
        """Update the remote warning label when status changes."""
        try:
            warning_lbl = self.query_one("#lbl_remote_warning", Label)
            warning_lbl.update(status)
            warning_lbl.display = bool(status)
        except Exception:
            pass

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
        user_text = self._resolve_regeneration_text(user_text)
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

    def get_last_user_message_from_ui(self) -> str | None:
        """Retrieve the raw content of the last user bubble from the UI."""
        try:
            user_bubbles = self.query(".user_bubble")
            if user_bubbles:
                last_bubble = user_bubbles.last()
                if hasattr(last_bubble, "raw_text"):
                    return last_bubble.raw_text
        except Exception:
            pass
        return None

    def _resolve_regeneration_text(self, engine_text: str | None) -> str | None:
        """Resolve the text to use for regeneration, falling back to the UI's last user message if needed."""
        ui_text = self.get_last_user_message_from_ui()
        if ui_text:
            if not engine_text or engine_text != ui_text:
                return ui_text
        return engine_text

    def action_open_profile_select(self) -> None:
        """Open the profile selection screen."""
        from ui.ProfileSelectScreen import ProfileSelect
        self.push_screen(ProfileSelect(), callback=self.on_profile_selected)

    def action_open_settings(self) -> None:
        """Open the global settings screen."""
        from ui.SettingsScreen import SettingsScreen
        self.push_screen(SettingsScreen(), callback=self.on_settings_saved)

    def on_settings_saved(self, result: dict | None) -> None:
        """Callback handled when SettingsScreen is dismissed with saved changes."""
        if not result:
            return

        self.add_message("✓ Settings saved successfully", role="system")

        # Sync Main TUI settings sidebar widgets with new settings
        try:
            self.query_one("#sw_tts", Switch).value = result.get("tts_enabled", False)
            self.query_one("#sw_dialogue", Switch).value = result.get("character_speak", True)
            self.query_one("#sw_narration", Switch).value = result.get("speak_narration", True)
            self.query_one("#sw_privacy", Switch).value = result.get("privacy_mode", False)
            self.query_one("#interaction_mode_select", Select).value = result.get("interaction_mode", "rp")

            self.query_one("#model_select", Select).value = result.get("default_llm_model")
            self.query_one("#tts_engine_select", Select).value = result.get("default_tts_engine")
            self.query_one("#character_voice_select", Select).value = result.get("default_tts_voice")
            self.query_one("#narration_voice_select", Select).value = result.get("narration_tts_voice")
            self.query_one("#image_protocol_select", Select).value = result.get("image_protocol")
        except Exception:
            pass

        # Update character profile settings locally if character active
        if self.character_profile and self.char_path:
            self.character_profile["llm_model"] = result.get("default_llm_model")
            self.character_profile["tts_engine"] = result.get("default_tts_engine")
            self.character_profile["preferred_edge_voice"] = result.get("default_tts_voice")
            from engines.utilities import save_json_atomic
            save_json_atomic(self.char_path, self.character_profile)

        # Apply settings changes live
        self.remount_avatar_widgets()
        self.update_sidebar()

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
                    yield self._build_avatar_widget(self._current_char_avatar_path, "avatar_portrait_character")
                yield Label("Name: [bold magenta]None[/bold magenta]", id="lbl_char")
                yield Label("Status: [bold]Neutral[/bold]", id="lbl_status")
                yield Label("Relationship:", classes="sidebar_label")
                yield ProgressBar(total=200, show_percentage=False, id="rel_bar")
                yield Label("Score: [bold]0[/bold]", id="lbl_rel")

                yield Label("", id="lbl_remote_warning", classes="remote_warning")

                yield Label("--- User ---", classes="sidebar_header")
                with Vertical(id="user_avatar_wrap", classes="avatar_container"):
                    yield self._build_avatar_widget(self._current_user_avatar_path, "avatar_portrait_user")
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

                with Horizontal(classes="setting_row"):
                    yield Label("Privacy Mode:", classes="setting_label")
                    yield Switch(value=get_setting("privacy_mode", False), id="sw_privacy")

                yield Label("Interaction Mode:", classes="sidebar_label")
                yield Select([], id="interaction_mode_select", prompt="Select Mode")

                yield Label("Image Protocol:", classes="sidebar_label")
                yield Select([], id="image_protocol_select", prompt="Select Image Protocol")

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
            from ui.ProfileSelectScreen import ProfileSelect
            self.push_screen(ProfileSelect(), callback=self.on_profile_selected)
            return

        self.populate_models()
        self.populate_voices()
        self.populate_tts_engines()
        self.populate_image_protocols()
        self.populate_interaction_modes()

        # Start usage metrics update loop
        self.set_interval(2.0, self.update_usage_metrics)

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
        self.populate_image_protocols()
        self.populate_interaction_modes()

    @staticmethod
    def format_summary(summary: str) -> str:
        return TextFormatter.format_summary(summary)

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
        
        formatter = TextFormatter(
            user_name=user_name,
            character_name=character_name,
            user_speech_color=user_speech_color,
            assistant_speech_color=assistant_speech_color,
        )
        return formatter.format_rp(text, role)

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
        elif event.switch.id == "sw_privacy":
            update_setting("privacy_mode", event.value)
            self.add_message(f"Privacy Mode: {'[bold green]ON[/bold green]' if event.value else '[bold red]OFF[/bold red]'}", role="system")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Update the character profile with selected LLM, Character Voice, or Narration Voice."""
        from engines.utilities import save_json_atomic

        # Handle cases where value might be Select.BLANK (NULL)
        val = event.value if event.value != Select.BLANK else None

        if event.select.id == "model_select":
            if val is not None:
                self.character_profile["llm_model"] = val
                save_json_atomic(self.char_path, self.character_profile)
                self.add_message(f"LLM model switched to [bold]{val}[/bold]", role="system")
            else:
                event.select.value = self.character_profile.get("llm_model") if self.character_profile else get_setting("default_llm_model", "llama3")
        elif event.select.id == "character_voice_select":
            if val is not None:
                self.character_profile["preferred_edge_voice"] = val
                save_json_atomic(self.char_path, self.character_profile)
                self.add_message(f"Companion voice set to [bold]{val}[/bold]", role="system")
            else:
                event.select.value = self.character_profile.get("preferred_edge_voice") if self.character_profile else get_setting("narration_tts_voice", "en-US-AndrewNeural")
        elif event.select.id == "narration_voice_select":
            if val is not None:
                if update_setting("narration_tts_voice", val):
                    self.add_message(f"Narration voice set to [bold]{val}[/bold]", role="system")
                else:
                    self.add_message(f"Failed to set narration voice to [bold]{val}[/bold]", role="system")
            else:
                event.select.value = get_setting("narration_tts_voice", "en-US-AndrewNeural")
        elif event.select.id == "tts_engine_select":
            if val is not None:
                self.character_profile["tts_engine"] = val
                save_json_atomic(self.char_path, self.character_profile)
                self.add_message(f"TTS engine switched to [bold]{val}[/bold]", role="system")
            else:
                event.select.value = self.character_profile.get("tts_engine") if self.character_profile else get_setting("default_tts_engine", "edge-tts")
        elif event.select.id == "image_protocol_select":
            if val is not None:
                valid_protocols = {value for _, value in self.IMAGE_PROTOCOLS}
                if val in valid_protocols and update_setting("image_protocol", val):
                    self.remount_avatar_widgets()
                    self.add_message(f"Image protocol set to [bold]{val}[/bold]", role="system")
                else:
                    self.add_message(f"Failed to set image protocol to [bold]{val}[/bold]", role="system")
            else:
                event.select.value = get_setting("image_protocol", "auto")
        elif event.select.id == "interaction_mode_select":
            if val is not None:
                if update_setting("interaction_mode", val):
                    self.add_message(f"Interaction mode set to [bold]{val.upper()}[/bold]", role="system")
                else:
                    self.add_message(f"Failed to set interaction mode to [bold]{val.upper()}[/bold]", role="system")
            else:
                event.select.value = get_setting("interaction_mode", "rp")

    def populate_image_protocols(self) -> None:
        """Populate image protocol selection and sync current setting."""
        select = self.query_one("#image_protocol_select", Select)
        select.set_options(self.IMAGE_PROTOCOLS)
        valid_protocols = {value for _, value in self.IMAGE_PROTOCOLS}
        current_protocol = get_setting("image_protocol", "auto")
        if current_protocol not in valid_protocols:
            current_protocol = "auto"
        select.value = current_protocol

    def populate_interaction_modes(self) -> None:
        """Populate interaction mode selection and sync current setting."""
        try:
            select = self.query_one("#interaction_mode_select", Select)
            select.set_options(self.INTERACTION_MODES)
            current_mode = get_setting("interaction_mode", "rp")
            if current_mode not in ("rp", "casual"):
                current_mode = "rp"
            select.value = current_mode
        except Exception:
            pass

    def start_tts_worker(self) -> None:
        """Starts a worker thread for TTS generation and playback."""
        threading.Thread(target=self.tts_generation_worker, daemon=True).start()
        threading.Thread(target=self.tts_playback_worker, daemon=True).start()

    def tts_generation_worker(self) -> None:
        """Worker thread for generating TTS audio files."""
        while True:
            data = self.tts_text_queue.get()
            if data is None: break
            text, voice, engine, clone_ref, language, user_name = data
            temp_filename = os.path.join(os.environ.get("TEMP", "/tmp"), f"tts_{time.time()}.mp3")
            if generate_audio(text, temp_filename, voice=voice, engine=engine, clone_ref=clone_ref, language=language, user_name=user_name):
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
                                        relationship_score=self.character_profile.get("relationship_score", 0))

    def run_recap(self):
        messages_history = memory_manager.load_history(self.history_profile_name)
        if not messages_history:
            return

        # Check if we have an existing persistent summary
        memory_core = memory_manager.get_memory_core(self.history_profile_name)
        last_index = memory_manager.get_last_summarized_index(self.history_profile_name)
        
        # Defensive check against mocks in unit tests
        if not isinstance(memory_core, str):
            memory_core = ""
        if not isinstance(last_index, int):
            last_index = 0

        short_limit = 15

        if len(messages_history) <= short_limit:
            # Short history: show all in full
            self.add_message(f"--- Recap: {len(messages_history)} messages loaded ---", role="system")
            for index, msg_data in enumerate(messages_history, start=1):
                role = msg_data.get("role", "assistant")
                content = msg_data.get("content", "")
                if role != "system":
                    content = self.format_rp(content, role=role)
                message_number = index if role in ("user", "assistant") else None
                self.add_message(content, role=role, msg_data=msg_data, message_number=message_number)
            self.add_message("--- Recap complete ---", role="system")
            return

        # Long history: check memory core
        if memory_core:
            new_messages_count = len(messages_history) - last_index
            if new_messages_count <= short_limit:
                # Not enough new messages to warrant updating summary on boot.
                # Display the cached summary instantly and show the new messages in full.
                self.add_message("--- Recap: Memory Core (Loaded instantly) ---", role="system")
                self.add_message(self.format_summary(memory_core), role="summary")
                self.add_message("--- Recent Continuity ---", role="system")
                
                recent_history = messages_history[last_index:]
                for offset, msg_data in enumerate(recent_history):
                    role = msg_data.get("role", "assistant")
                    content = msg_data.get("content", "")
                    if role != "system":
                        content = self.format_rp(content, role=role)
                    message_number = last_index + 1 + offset if role in ("user", "assistant") else None
                    self.add_message(content, role=role, msg_data=msg_data, message_number=message_number)
                
                self.add_message("--- Recap complete ---", role="system")
                return

        # Fallback to background summarization if no summary exists or too many new messages accumulated
        recap_state = split_recap_history(messages_history, short_history_limit=short_limit, recent_window=5)
        self.add_message("--- [bold cyan]Analyzing past memories...[/bold cyan] ---", role="system")
        self.summarize_and_display(
            recap_state["older_history"],
            recap_state["recent_history"],
            recap_state["recent_start_index"],
            existing_core=memory_core,
            last_summarized_index=last_index
        )

    @work(thread=True)
    def summarize_and_display(self, older_history: list, recent_history: list, recent_start_index: int, existing_core: str = "", last_summarized_index: int = 0):
        """Worker for summarizing history in the background."""
        if existing_core:
            # Incremental update: summarize only new messages up to older_history end
            new_messages_to_sum = older_history[last_summarized_index:]
            if new_messages_to_sum:
                summary = generate_updated_memory_core(
                    existing_core,
                    new_messages_to_sum,
                    user_name=self.user_name,
                    char_name=self.ch_name,
                )
                # Persist the update
                new_last_index = len(older_history)
                memory_manager.update_memory_core(self.history_profile_name, summary, new_last_index)
            else:
                summary = existing_core
        else:
            summary = generate_recap_summary(older_history, user_name=self.user_name, char_name=self.ch_name)
            # Save the initial memory core
            new_last_index = len(older_history)
            memory_manager.update_memory_core(self.history_profile_name, summary, new_last_index)

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

    @work(thread=True)
    def _sync_lore_worker(self, remote_url: str, lorebook_data: dict) -> None:
        """Worker for syncing lore to remote bridge in the background."""
        try:
            success = sync_lore_to_remote(lorebook_data, remote_url)
            if success:
                self.app.call_from_thread(
                    lambda: self.add_message("✓ Lore synced to remote bridge", role="system")
                )
        except Exception as e:
            if get_setting("debug_mode", False):
                print(f"Lore sync worker error: {e}")

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
        memory_manager.clear_pending_user_message(self.history_profile_name)
        update_setting("current_character_profile", os.path.basename(self.char_path))

        if self.user_path:
            update_setting("current_user_profile", os.path.basename(self.user_path))
        else:
            self.user_name = "User"

        self.update_sidebar()
        self.add_message(f"Loaded character profile: [bold]{self.ch_name}[/bold]", role="system")

        # Sync lore to remote bridge if configured
        remote_url = get_setting("remote_llm_url")
        if remote_url and self.character_profile:
            lore_file = self.character_profile.get("lorebook_path") or "lorebooks/default.json"
            lorebook_data = load_lorebook(lore_file)
            if lorebook_data.get("entries"):
                self._sync_lore_worker(remote_url, lorebook_data)


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
                self._current_char_avatar_path = state["char_avatar_abs"]
                self._set_avatar_image("char_avatar_wrap", "avatar_portrait_character", state["char_avatar_abs"])

            if getattr(self, "_current_user_avatar_path", None) != state["user_avatar_abs"]:
                self._current_user_avatar_path = state["user_avatar_abs"]
                self._set_avatar_image("user_avatar_wrap", "avatar_portrait_user", state["user_avatar_abs"])
        except Exception:
            pass

        self.query_one("#lbl_char").update(state["char_label"])
        self.query_one("#lbl_status").update(state["status_label"])
        self.query_one("#lbl_rel").update(state["rel_label"])
        self.query_one("#lbl_user").update(state["user_label"])
        self.query_one("#rel_bar").progress = state["rel_progress"]

        # Update remote status warning (VULN-004)
        remote_llm = get_setting("remote_llm_url")
        remote_tts = get_setting("remote_tts_url")
        if remote_llm or remote_tts:
            services = []
            if remote_llm: services.append("LLM")
            if remote_tts: services.append("TTS")
            self.remote_status = f"[bold red]Remote Active: {', '.join(services)}[/bold red]\n[dim]Data is sent to remote URLs.[/dim]"
        else:
            self.remote_status = ""

    def add_message(self, text, role="user", msg_data=None, message_number: int | None = None, raw_text: str | None = None):
        if role not in ("system", "command", "tip_message"):
            import re
            is_formatted = False
            if "[" in text and "]" in text:
                if re.search(r"\[(?:/?[ib]|/?[a-zA-Z#][^\]]*)\]", text):
                    is_formatted = True
            if not is_formatted or "{{" in text or role == "summary":
                text = self.format_rp(text, role=role)

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
            if role == "user":
                bubble.raw_text = raw_text or (msg_data.get("content") if msg_data else text)
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
        self.add_message(display_message, role="user", message_number=user_message_number, raw_text=message)

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
                user_text = command_action.get("user_text")
                user_text = self._resolve_regeneration_text(user_text)
                if user_text:
                    self.stream_response(user_text, is_regeneration=True)
                return

            if command_action["type"] == "rewind":
                self.reload_chat_from_history()
                self.check_for_rolling_summary()
                self.add_message(
                    f"[SYSTEM] Rewound conversation from {command_action['original_count']} to {command_action['kept_count']} messages.",
                    role="command",
                )
                return

            if command_action["type"] == "open_settings":
                self.action_open_settings()
                return

            if command_action["type"] == "compress":
                self.add_message("[SYSTEM] Starting manual history compression...", role="command")
                self.run_manual_compression()
                return

            if command_action["type"] == "command_noop":
                self.add_message("[SYSTEM] Recognized command pattern but no action taken: Non-existent command.", role="command")
                return

        # Trigger AI response
        if not message.startswith("//"):
            memory_manager.set_pending_user_message(self.history_profile_name, message)

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
        self.response_worker(message, is_regeneration, container, ai_msg, header)

    @work(exclusive=True, thread=True)
    def response_worker(
        self,
        message: str,
        is_regeneration: bool,
        container: ScrollableContainer,
        ai_msg: Static,
        header: str,
    ) -> None:
        """Worker to handle the LLM streaming and TTS queuing."""
        full_response = ""
        user_name = self.user_profile.get("name", "User") if self.user_profile else "User"

        for event in iterate_response_events(
            message=message,
            character_profile=self.character_profile,
            history_profile_name=self.history_profile_name,
            is_regeneration=is_regeneration,
            user_name=user_name,
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

    def _get_local_metrics(self) -> tuple[float, float]:
        """Fetch local CPU and RAM usage on Windows using ctypes, or return fallback values."""
        if sys.platform != "win32":
            return 0.0, 0.0

        import ctypes

        # Memory Info
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ('dwLength', ctypes.c_ulong),
                ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', ctypes.c_uint64),
                ('ullAvailPhys', ctypes.c_uint64),
                ('ullTotalPageFile', ctypes.c_uint64),
                ('ullAvailPageFile', ctypes.c_uint64),
                ('ullTotalVirtual', ctypes.c_uint64),
                ('ullAvailVirtual', ctypes.c_uint64),
                ('ullAvailExtendedVirtual', ctypes.c_uint64),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        try:
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            ram = float(stat.dwMemoryLoad)
        except Exception:
            ram = 0.0

        # CPU Info (calculates delta between two snapshots)
        class FILETIME(ctypes.Structure):
            _fields_ = [('dwLowDateTime', ctypes.c_ulong), ('dwHighDateTime', ctypes.c_ulong)]

        def to_int(ft):
            return (ft.dwHighDateTime << 32) + ft.dwLowDateTime

        idle1 = FILETIME()
        kernel1 = FILETIME()
        user1 = FILETIME()
        try:
            ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle1), ctypes.byref(kernel1), ctypes.byref(user1))
            time.sleep(0.05)
            idle2 = FILETIME()
            kernel2 = FILETIME()
            user2 = FILETIME()
            ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle2), ctypes.byref(kernel2), ctypes.byref(user2))

            idle_diff = to_int(idle2) - to_int(idle1)
            kernel_diff = to_int(kernel2) - to_int(kernel1)
            user_diff = to_int(user2) - to_int(user1)

            sys_diff = kernel_diff + user_diff
            if sys_diff > 0:
                cpu = ((sys_diff - idle_diff) * 100.0) / sys_diff
            else:
                cpu = 0.0
        except Exception:
            cpu = 0.0

        return cpu, ram

    @work(exclusive=True, thread=True)
    def update_usage_metrics(self) -> None:
        """Background worker to query system resources and remote bridge status periodically."""
        cpu, ram = self._get_local_metrics()

        # Check remote bridge status
        remote_url = get_setting("remote_llm_url")
        vram_info = ""
        if remote_url:
            import requests
            try:
                resp = requests.get(f"{remote_url.rstrip('/')}/health", timeout=1.5)
                if resp.status_code == 200:
                    data = resp.json()
                    gpus = data.get("gpus", [])
                    if gpus:
                        if len(gpus) > 1:
                            vram_strings = [f"GPU{g['id']}: {g['allocated_gib']:.1f}/{g['total_gib']:.1f} GB" for g in gpus]
                            vram_info = " | Bridge VRAM: " + " | ".join(vram_strings)
                        else:
                            g = gpus[0]
                            vram_info = f" | Bridge VRAM: {g['allocated_gib']:.1f}/{g['total_gib']:.1f} GB"
                    else:
                        vram_info = " | Bridge: Online"
                else:
                    vram_info = " | Bridge: Error"
            except Exception:
                vram_info = " | Bridge: Offline"

        metric_str = f"CPU: {cpu:.0f}% | RAM: {ram:.0f}%{vram_info}"

        def apply_update():
            # Update the title bar of the terminal dynamically
            self.title = "t.ai"
            self.sub_title = metric_str

        self.app.call_from_thread(apply_update)

    def run_manual_compression(self) -> None:
        """Resolves active session history length and triggers manual summarization."""
        history_len = memory_manager.get_history_length(self.history_profile_name)
        last_index = memory_manager.get_last_summarized_index(self.history_profile_name)

        # We need at least 5 messages in history, and we want to keep at least 3 messages active
        min_active_context = 3
        if history_len <= 4:
            self.add_message("[SYSTEM] Conversation history is too short to compress.", role="command")
            return

        to_summarize_count = history_len - min_active_context
        if to_summarize_count <= last_index:
            self.add_message("[SYSTEM] No new messages to compress since the last summarization.", role="command")
            return

        full_history = memory_manager.load_history(self.history_profile_name)
        new_messages_to_sum = full_history[last_index:to_summarize_count]
        self.perform_manual_compression(new_messages_to_sum, to_summarize_count)

    @work(thread=True)
    def perform_manual_compression(self, new_messages: list, new_index: int) -> None:
        """Background worker to run manual history compression."""
        existing_core = memory_manager.get_memory_core(self.history_profile_name)
        try:
            new_core = generate_updated_memory_core(
                existing_core,
                new_messages,
                user_name=self.user_name,
                char_name=self.ch_name,
            )
            memory_manager.update_memory_core(self.history_profile_name, new_core, new_index)
            self.app.call_from_thread(
                self.add_message,
                f"✓ Context successfully compressed. Memory Core updated to index {new_index}.",
                role="command"
            )
        except Exception as e:
            self.app.call_from_thread(
                self.add_message,
                f"[ERROR] Context compression failed: {e}",
                role="command"
            )


if __name__ == "__main__":
    app = TaiMenu(char_path=None, user_path=None)
    app.run()
