"""
Main menu and TUI components for the AI Desktop Companion.
"""
# Standard library imports
import json
import re
import os
import queue
import random
import threading
import time
import sys
from pathlib import Path

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
from engines.app_commands import app_commands, RestartRequested
from engines.config import update_setting, get_setting
from engines.responses import get_respond_stream, generate_summary, update_rolling_summary
from engines.tts_module import generate_audio, play_audio, clean_text_for_tts
from engines.memory_v2 import memory_manager
from engines.prompts import get_mood_rule

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
    ]

    show_sidebar = reactive(True)

    CSS_PATH = "tcss/menu.tcss"

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
        self.char_path = char_path
        self.user_path = user_path
        
        if not self.char_path:
            char_profile_name = get_setting("current_character_profile")
            if char_profile_name:
                potential_path = os.path.join("profiles", char_profile_name)
                if os.path.exists(potential_path):
                    self.char_path = potential_path

        if not self.user_path:
            user_profile_name = get_setting("current_user_profile")
            if user_profile_name:
                potential_path = os.path.join("user_profiles", user_profile_name)
                if os.path.exists(potential_path):
                    self.user_path = potential_path

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

    def action_open_profile_select(self) -> None:
        """Open the profile selection screen."""
        from ProfileSelectScreen import ProfileSelect
        self.push_screen(ProfileSelect(), callback=self.on_profile_selected)

    def compose(self) -> ComposeResult:
        # Get initial avatar path for character and user profiles (if they exist) to display in the sidebar
        init_avatar = "img/No_Image_Error.png"
        init_user_avatar = "img/No_Image_Error.png"

        if self.char_path:
            try:
                with open(self.char_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    path = data.get("avatar_path")
                    if path and os.path.exists(path):
                        init_avatar = path
            except (FileNotFoundError, json.JSONDecodeError):
                pass

        if self.user_path:
            try:
                with open(self.user_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    path = data.get("avatar_path")
                    if path and os.path.exists(path):
                        init_user_avatar = path
            except (FileNotFoundError, json.JSONDecodeError):
                pass

        self._current_char_avatar_path = str(Path(init_avatar).absolute())
        self._current_user_avatar_path = str(Path(init_user_avatar).absolute())

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

    @staticmethod
    def format_summary(summary: str) -> str:
        # Handle ## headers (Markdown style)
        text = re.sub(r'^##\s+(.*)$', r'[b][u]\1[/u][/b]', summary, flags=re.MULTILINE)
        # Handle **bold**
        text = re.sub(r'\*\*(.*?)\*\*', r'[b]\1[/b]', text, flags=re.DOTALL)
        # Convert * to bullet points
        text = text.replace("*", "•")
        return text

    def format_rp(self, text, role) -> str:
        """
        Formats text with basic markdown-like syntax for the TUI.
        - **bold** -> [b]bold[/b]
        - *italic* -> [i][dim]italic[/dim][/i] (Narration)
        - "speech" -> [yellow]"speech"[/yellow] (Highlight)
        """
        if not text:
            return ""

        user = self.user_profile.get("name", "User") if self.user_profile else "User"
        character = self.character_profile.get("name", "Assistant") if self.character_profile else "Assistant"

        # Replace placeholder tags like {{user}} with actual value
        text = text.replace("{{user}}", user).replace("{{char}}", character)
        text = text.replace("{{User}}", user).replace("{{Char}}", character)

        # 1. Strip [SCENE: ...] tags
        text = re.sub(r'\[SCENE:\s*.*?\]', '', text, flags=re.IGNORECASE).strip()

        # 2. Bold: **text**
        text = re.sub(r'\*\*(.*?)\*\*', r'[b]\1[/b]', text, flags=re.DOTALL)

        # 2. Italic/Narration: *text* (matches single * only, ensuring it's not part of **)
        text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'[i][dim]\1[/dim][/i]', text, flags=re.DOTALL)

        # 3. Speech: "text" or “text” -> Highlight dialogue for better readability
        if role == "assistant":
            speech_color = self.character_profile.get("colors", {}).get("speech_highlight", "yellow")
        else:
            speech_color = "yellow"
            if self.user_profile:
                speech_color = self.user_profile.get("colors", {}).get("speech_highlight", "yellow")
        text = re.sub(r'["“](.*?)["”]', fr'[{speech_color}]"\1"[/{speech_color}]', text, flags=re.DOTALL)

        return text

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
            self.add_message(self.format_rp(starter_messages[0], role="assistant"), role="assistant")
            memory_manager.save_history(self.history_profile_name, [{"role": "assistant",
                                                                     "content": starter_messages[0]}],
                                        mood_score=self.character_profile.get("relationship_score", 0))

    def run_recap(self):
        messages_history = memory_manager.load_history(self.history_profile_name)
        if not messages_history:
            return

        if len(messages_history) <= 15:
            self.add_message(f"--- Recap: {len(messages_history)} messages loaded ---", role="system")
            for msg_data in messages_history:
                role = msg_data.get("role", "assistant")
                content = msg_data.get("content", "")
                if role != "system":
                    content = self.format_rp(content, role=role)
                self.add_message(content, role=role)
            self.add_message("--- Recap complete ---", role="system")
        else:
            # History is long, trigger summarization (Split: older history vs. recent 5)
            older_history = messages_history[:-5]
            recent_history = messages_history[-5:]

            self.add_message("--- [bold cyan]Analyzing past memories...[/bold cyan] ---", role="system")
            self.summarize_and_display(older_history, recent_history)

    @work(thread=True)
    def summarize_and_display(self, older_history: list, recent_history: list):
        """Worker for summarizing history in the background."""
        # Default to gemma2:2b for efficient summarization
        summarizer_model = get_setting("summarizer_model", "gemma2:2b")
        remote_url = get_setting("remote_llm_url")
        
        summary = generate_summary(older_history, model=summarizer_model, remote_url=remote_url, 
                                   user_name=self.user_name, char_name=self.ch_name)
        
        def update_ui():
            self.add_message(self.format_summary(summary), role="summary")
            self.add_message("--- Recent Continuity ---", role="system")
            for msg_data in recent_history:
                role = msg_data.get("role", "assistant")
                content = msg_data.get("content", "")
                if role != "system":
                    content = self.format_rp(content, role=role)
                self.add_message(content, role=role)
            self.add_message("--- Recap complete ---", role="system")

        self.app.call_from_thread(update_ui)

    def load_initial_state(self) -> None:
        """Loads profiles and settings based on pre-selected paths or settings.json."""
        if not self.char_path:
            char_profile_name = get_setting("current_character_profile")
            if char_profile_name:
                potential_path = os.path.join("profiles", char_profile_name)
                if os.path.exists(potential_path):
                    self.char_path = potential_path

        if not self.user_path:
            user_profile_name = get_setting("current_user_profile")
            if user_profile_name:
                potential_path = os.path.join("user_profiles", user_profile_name)
                if os.path.exists(potential_path):
                    self.user_path = potential_path

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

        with open(self.char_path, "r", encoding="utf-8") as f:
            self.character_profile = json.load(f)

        self.ch_name = self.character_profile.get("name", "Assistant")
        colors = self.character_profile.get("colors", {})
        self.char_name_lbl_color = colors.get("name_lbl", "magenta")
        self.history_profile_name = os.path.basename(self.char_path).replace(".json", "")
        update_setting("current_character_profile", os.path.basename(self.char_path))

        if self.user_path:
            with open(self.user_path, "r", encoding="utf-8") as f:
                self.user_profile = json.load(f)
            self.user_name = self.user_profile.get("name", "User")
            self.user_name_lbl_color = self.user_profile.get("colors", {}).get("name_lbl", "cyan")
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

        # Load history recap if enabled
        if get_setting("auto_recap_on_start", False) and has_history:
            self.run_recap()

        # Print tip message
        self.add_message("Tip: Use [bold]Ctrl+J[/bold] for a newline.", role="tip_message")

    def update_sidebar(self):
        """Update the sidebar content including avatars and relationship stats."""
        # Refresh avatars
        try:
            # Character Avatar
            char_avatar_path = self.character_profile.get("avatar_path", "img/No_Image_Error.png")
            if not char_avatar_path or not os.path.exists(char_avatar_path): 
                char_avatar_path = "img/No_Image_Error.png"
            
            char_abs_path = str(Path(char_avatar_path).absolute())
            
            if getattr(self, "_current_char_avatar_path", None) != char_abs_path:
                char_img = self.query_one("#avatar_portrait_character", Image)
                char_img.image = char_abs_path
                self._current_char_avatar_path = char_abs_path

            # User Avatar
            user_avatar_path = "img/No_Image_Error.png"
            if self.user_profile:
                user_avatar_path = self.user_profile.get("avatar_path", "img/No_Image_Error.png")
                if not user_avatar_path or not os.path.exists(user_avatar_path): 
                    user_avatar_path = "img/No_Image_Error.png"
            
            user_abs_path = str(Path(user_avatar_path).absolute())
            
            if getattr(self, "_current_user_avatar_path", None) != user_abs_path:
                user_img = self.query_one("#avatar_portrait_user", Image)
                user_img.image = user_abs_path
                self._current_user_avatar_path = user_abs_path
        except Exception as e:
            # For debugging
            # self.log(f"Error updating avatars: {e}")
            pass

        rel = self.character_profile.get("relationship_score", 0)
        
        # Determine relationship label and color from centralized config
        mood_rule = get_mood_rule(rel)
        rel_label = mood_rule.get("label", "Neutral / Acquaintance")
        rel_color = mood_rule.get("color", "#6e88ff")

        self.query_one("#lbl_char").update(f"Name: [bold {self.char_name_lbl_color}]{self.ch_name}[/bold {self.char_name_lbl_color}]")
        self.query_one("#lbl_mood").update(f"Mood: [bold {rel_color}]{rel_label}[/bold {rel_color}]")
        self.query_one("#lbl_rel").update(f"Score: [bold]{rel}[/bold]")
        self.query_one("#lbl_user").update(f"User: [bold {self.user_name_lbl_color}]{self.user_name}[/bold {self.user_name_lbl_color}]")
        
        # Update progress bar (Map -100/100 to 0/200)
        self.query_one("#rel_bar").progress = rel + 100

    def add_message(self, text, role="user"):
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
            name = self.user_name if role == "user" else self.ch_name
            name_color = self.user_name_lbl_color if role == "user" else self.char_name_lbl_color
            
            bubble = Static(f"[bold {name_color}]{name}:[/bold {name_color}]\n{text}", markup=True, classes=f"message {bubble_class}")
            row = Horizontal(bubble, classes=f"message_row {row_class}")
            
            container.mount(row)
            
        container.scroll_end(animate=False)

    async def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        """Handles user input submission from ChatInput."""
        message = event.value.strip()
        if not message: return

        # Format user message for display
        display_message = self.format_rp(message, role="user")
        self.add_message(display_message, role="user")

        # Handle commands (original message)
        if message.startswith("//"):
            try:
                success, messages = app_commands(message, suppress_output=True)
                if success:
                    for msg in messages:
                        self.add_message(msg, role="command")
                    self.update_sidebar()
                    return
            except RestartRequested:
                self.exit()
                raise
        
        # Trigger AI response
        self.stream_response(message)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Fallback for any standard Input widgets (legacy or other)."""
        # Create a mock event to reuse logic if needed, or just redirect
        class MockEvent:
            def __init__(self, value):
                self.value = value
        await self.on_chat_input_submitted(MockEvent(event.value))
        
    @work(thread=True)
    def stream_response(self, message: str) -> None:
        """Worker to handle the LLM streaming and TTS queuing"""

        def _get_smart_split_points(text):
            """
            Internal helper function to find split points for TTS.
            Splits on asterisks (to switch voices) and punctuation (to keep segments short).
            """
            points = []
            in_asterisks = False
            for i in range(len(text)):
                char = text[i]
                if char == '*':
                    in_asterisks = not in_asterisks
                    points.append(i + 1)
                    continue
                if not in_asterisks:
                    if char in ".!?\n":
                        if char == '.' and i + 1 < len(text) and text[i + 1] == '.':
                            continue
                        if char == '.' and i > 0 and text[i - 1] == '.':
                            continue
                        points.append(i + 1)
            return points

        container = self.query_one("#chat_list")
        
        ai_msg = Static(f"[bold {self.char_name_lbl_color}]{self.ch_name}:[/bold {self.char_name_lbl_color}]\n", markup=True, classes="message ai_bubble")
        row = Horizontal(ai_msg, classes="message_row ai_row")
        
        self.app.call_from_thread(container.mount, row)
        self.app.call_from_thread(container.scroll_end, animate=False)

        full_response = ""
        current_buffer = ""
        tts_in_narration = False

        # Get setting for TTS
        char_voice = self.character_profile.get("preferred_edge_voice", None)
        char_engine = self.character_profile.get("tts_engine", "edge-tts")
        char_clone_ref = self.character_profile.get("voice_clone_ref", None)
        char_language = self.character_profile.get("tts_language", "en")
        speak_enable = get_setting("character_speak", False)

        narrator_voice = get_setting("narration_tts_voice", "en-US-AndrewNeural")
        narrator_engine = "edge-tts"
        narration_enable = get_setting("speak_narration", False)


        for chunk in get_respond_stream(message, self.character_profile, history_profile_name=self.history_profile_name):
            full_response += chunk
            current_buffer += chunk

            # Update UI from thread
            self.app.call_from_thread(ai_msg.update, f"[bold {self.char_name_lbl_color}]{self.ch_name}:[/bold {self.char_name_lbl_color}]\n{self.format_rp(full_response, role='assistant')}")
            self.app.call_from_thread(container.scroll_end, animate=False)

            # ---------------------------------------------------------------
            # Check for split points for TTS
            if get_setting("tts_enabled", False):
                split_points = _get_smart_split_points(current_buffer)
                if split_points:
                    last_point = 0
                    for point in split_points:
                        segment = current_buffer[last_point:point]

                        voice = narrator_voice if tts_in_narration else char_voice
                        engine = narrator_engine if tts_in_narration else char_engine
                        clone_ref = None if tts_in_narration else char_clone_ref
                        language = "en" if tts_in_narration else char_language

                        if '*' in segment:
                            tts_in_narration = not tts_in_narration

                        cleaned = clean_text_for_tts(segment, speak_narration=True)
                        if cleaned:
                            # Only narration enabled: send segments that were narration before toggle
                            if not speak_enable and narration_enable and (voice == narrator_voice):
                                self.tts_text_queue.put((cleaned, voice, engine, clone_ref, language))
                            # Only character speech enabled: send segments that were dialogue before toggle
                            elif speak_enable and not narration_enable and (voice == char_voice):
                                self.tts_text_queue.put((cleaned, voice, engine, clone_ref, language))
                            # Both enabled: send everything
                            elif speak_enable and narration_enable:
                                self.tts_text_queue.put((cleaned, voice, engine, clone_ref, language))
                        last_point = point
                    current_buffer = current_buffer[last_point:]
            # ---------------------------------------------------------------

        # After the full response is printed, check if there's any leftover text
        if get_setting("tts_enabled", False) and current_buffer.strip():
            cleaned = clean_text_for_tts(current_buffer.strip(), speak_narration=True)
            if cleaned:
                # Use current state for final chunk
                voice = narrator_voice if tts_in_narration else char_voice
                engine = narrator_engine if tts_in_narration else char_engine
                clone_ref = None if tts_in_narration else char_clone_ref
                language = "en" if tts_in_narration else char_language
                self.tts_text_queue.put((cleaned, voice, engine, clone_ref, language))

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
        
        # We summarize if the unsummarized gap is larger than the window + buffer (5)
        if (history_len - last_index) > (limit + 5):
            # We want to summarize everything EXCEPT the last 'limit' messages 
            # which are kept in active context.
            to_summarize_count = history_len - limit
            if to_summarize_count > last_index:
                full_history = memory_manager.load_history(self.history_profile_name)
                # Messages to include in the NEW summary part
                new_messages_to_sum = full_history[last_index:to_summarize_count]
                
                self.perform_rolling_summary(new_messages_to_sum, to_summarize_count)

    @work(thread=True)
    def perform_rolling_summary(self, new_messages: list, new_index: int):
        """Background worker to update the Memory Core."""
        existing_core = memory_manager.get_memory_core(self.history_profile_name)
        summarizer_model = get_setting("summarizer_model", "gemma2:2b")
        remote_url = get_setting("remote_llm_url")
        
        new_core = update_rolling_summary(
            existing_core, 
            new_messages, 
            model=summarizer_model, 
            remote_url=remote_url,
            user_name=self.user_name,
            char_name=self.ch_name
        )
        
        # Persist the update
        memory_manager.update_memory_core(self.history_profile_name, new_core, new_index)
        self.log(f"Memory Core updated to index {new_index}")
