"""
Main menu and TUI components for the AI Desktop Companion.
"""
import json
import os
import queue
import random
import threading
import time
import sys


# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static, Label
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual import work

from engines.app_commands import app_commands
from engines.config import update_setting, get_setting
from engines.responses import get_respond_stream
from engines.tts_module import generate_audio, play_audio, clean_text_for_tts
from engines.utilities import pick_profile, pick_user_profile
from engines.memory_v2 import memory_manager


def get_smart_split_points(text):
    """
    Finds split points for TTS.
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
                if char == '.' and i + 1 < len(text) and text[i+1] == '.':
                    continue
                if char == '.' and i > 0 and text[i-1] == '.':
                    continue
                points.append(i + 1)
    return points

def format_rp(text):
    """Simple helper to convert *narration* to [i][dim]markup[/dim][/i]."""
    parts = text.split('*')
    result = ""
    for i, part in enumerate(parts):
        if i % 2 == 1:
            result += f"[i][dim]{part}[/dim][/i]"
        else:
            result += part
    return result

class TaiMenu(App):
    """t.ai - Logic-focused TUI implementation."""
    TITLE = "t.ai"

    CSS = """
    #app_body {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 35;
        height: 1fr;
    }
    #chat_container {
        height: 100%;
    }
    #chat_list {
        height: 1fr;
        border: solid $primary;
        padding: 1;
        overflow-y: scroll;
    }
    #status_sidebar {
        height: 100%;
        background: $panel;
        border-left: tall $accent;
        padding: 1;
    }
    .message_row {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }
    .user_row {
        align-horizontal: right;
    }
    .ai_row {
        align-horizontal: left;
    }
    .message {
        padding: 0 1;
        width: auto;
        max-width: 85%;
    }
    .user_bubble {
        color: $text;
        border: round $primary-lighten-2;
    }
    .ai_bubble {
        color: $text;
        border: round $primary-lighten-1;
    }
    .system_msg {
        color: $success;
        margin: 1 0;
        width: 100%;
        text-align: center;
    }
    Input {
        width: 100%;
        margin: 1 0;
    }
    Label {
        margin: 1 0;
    }
    """

    # Global TTS queue
    tts_text_queue = queue.Queue()
    audio_file_queue = queue.Queue()

    def __init__(self, char_path, user_path, **kwargs):
        super().__init__(**kwargs)
        self.char_path = char_path
        self.user_path = user_path
        self.character_profile = None
        self.user_profile = None
        self.ch_name = "Assistant"
        self.user_name = "User"
        self.history_profile_name = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="app_body"):
            with Vertical(id="chat_container"):
                with ScrollableContainer(id="chat_list"):
                    yield Label("[bold green]System:[/bold green] Waiting for profile...", id="init_msg", classes="system_msg")
                yield Input(placeholder="Type your message here...", id="user_input")
            with Vertical(id="status_sidebar"):
                yield Label("Companion: [bold]None[/bold]", id="lbl_char")
                yield Label("User: [bold]None[/bold]", id="lbl_user")
                yield Label("Relationship: [bold]0[/bold]", id="lbl_rel")
        yield Footer()

    def on_mount(self) -> None:
        """Initializes the app and load character profiles."""
        self.start_tts_worker()
        self.load_initial_state()

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
            self.add_message(format_rp(starter_messages[0]), role="assistant")
            memory_manager.save_history(self.history_profile_name, [{"role": "assistant",
                                                                     "content": starter_messages[0]}],
                                        mood_score=self.character_profile.get("relationship_score", 0))

    def run_recap(self):
        messages_history = memory_manager.load_history(self.history_profile_name)
        # If messages length is less than 15, just load everything to the chat list
        if messages_history and len(messages_history) <= 15:
            self.add_message(f"--- Recap: {len(messages_history)} messages loaded ---", role="system")
            for msg_data in messages_history:
                role = msg_data.get("role", "assistant")
                content = msg_data.get("content", "")
                if role != "system":
                    content = format_rp(content)
                self.add_message(content, role=role)
            self.add_message("--- Recap complete ---", role="system")
        else:
            # Anything more than 15 messages, let the AI context summarizer handle it
            # Will do soon, possibly with Microsoft's new BitNet
            pass

    def load_initial_state(self) -> None:
        """Loads profiles and settings based on pre-selected paths."""
        if not self.char_path:
            self.exit()
            return

        with open(self.char_path, "r", encoding="utf-8") as f:
            self.character_profile = json.load(f)

        self.ch_name = self.character_profile.get("name", "Assistant")
        self.history_profile_name = os.path.basename(self.char_path).replace(".json", "")
        update_setting("current_character_profile", os.path.basename(self.char_path))

        if self.user_path:
            with open(self.user_path, "r", encoding="utf-8") as f:
                self.user_profile = json.load(f)
            self.user_name = self.user_profile.get("name", "User")
            update_setting("current_user_profile", os.path.basename(self.user_path))
        else:
            self.user_name = "User"

        self.update_sidebar()
        self.query_one("#init_msg").update(f"[bold green]System:[/bold green] Loaded character profile: [bold]{self.ch_name}[/bold]")

        # Print character's starter messages and save to memory (if any, which should always be any)
        # Only do this if the history doesn't exist yet, to avoid repeating starter messages on every launch'
        has_history = memory_manager.has_history(self.history_profile_name)
        if not has_history:
            self.print_starter_message()

        # Load history recap if enabled
        if get_setting("auto_recap_on_start", False):
            self.run_recap()

    def update_sidebar(self):
        rel = self.character_profile.get("relationship_score", 0)
        self.query_one("#lbl_char").update(f"Companion: [bold magenta]{self.ch_name}[/bold magenta]")
        self.query_one("#lbl_user").update(f"User: [bold cyan]{self.user_name}[/bold cyan]")
        self.query_one("#lbl_rel").update(f"Relationship: [bold]{rel}[/bold]")

    def add_message(self, text, role="user"):
        container = self.query_one("#chat_list")
        if role == "system":
            container.mount(Static(text, markup=True, classes="system_msg"))
        else:
            row_class = "user_row" if role == "user" else "ai_row"
            bubble_class = "user_bubble" if role == "user" else "ai_bubble"
            name = self.user_name if role == "user" else self.ch_name
            name_color = "cyan" if role == "user" else "magenta"
            
            bubble = Static(f"[bold {name_color}]{name}:[/bold {name_color}]\n{text}", markup=True, classes=f"message {bubble_class}")
            row = Horizontal(bubble, classes=f"message_row {row_class}")
            
            container.mount(row)
            
        container.scroll_end(animate=False)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handles user input submission."""
        message = event.value.strip()
        if not message: return

        # Format user message for display
        display_message = format_rp(message)
        self.query_one(Input).value = ""
        self.add_message(display_message, role="user")

        # Handle commands (original message)
        if message.startswith("//"):
            if app_commands(message):
                self.update_sidebar()
                return
        
        # Trigger AI response
        self.stream_response(message)
        
    @work(thread=True)
    def stream_response(self, message: str) -> None:
        """Worker to handle the LLM streaming and TTS queuing"""
        container = self.query_one("#chat_list")
        
        ai_msg = Static(f"[bold magenta]{self.ch_name}:[/bold magenta]\n", markup=True, classes="message ai_bubble")
        row = Horizontal(ai_msg, classes="message_row ai_row")
        
        self.app.call_from_thread(container.mount, row)
        self.app.call_from_thread(container.scroll_end, animate=False)

        full_response = ""
        current_buffer = ""
        tts_in_narration = False

        # Get setting for TTS
        char_voice = self.character_profile.get("preferred_tts_voice", None)
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
            self.app.call_from_thread(ai_msg.update, f"[bold magenta]{self.ch_name}:[/bold magenta]\n{format_rp(full_response)}")
            self.app.call_from_thread(container.scroll_end, animate=False)

            # ---------------------------------------------------------------
            # Check for split points for TTS
            if get_setting("tts_enabled", False):
                split_points = get_smart_split_points(current_buffer)
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


if __name__ == "__main__":
    c_path = pick_profile()
    u_path = pick_user_profile() if c_path else None
    if c_path:
        app = TaiMenu(char_path=c_path, user_path=u_path)
        app.run()
