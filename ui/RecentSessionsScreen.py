import os
import json
from datetime import datetime
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Label, Button, OptionList
from textual.widgets.option_list import Option

def get_all_recent_sessions() -> list[dict]:
    """Scan all character profiles and retrieve all their session files sorted by last interaction time."""
    sessions = []
    profiles_dir = "profiles"
    history_dir = "history"
    
    if not os.path.exists(profiles_dir):
        return []
        
    profile_targets = []
    
    for entry in os.scandir(profiles_dir):
        if entry.is_file() and entry.name.endswith(".json") and entry.name != "settings.json":
            profile_file = entry.name
            profile_name = profile_file.replace(".json", "")
            
            # Check sessions directory for unified profile structure
            char_profile_dir = os.path.join(profiles_dir, profile_name)
            if os.path.isdir(char_profile_dir):
                sessions_dir = os.path.join(char_profile_dir, "sessions")
            else:
                sessions_dir = os.path.join(history_dir, profile_name)
            profile_targets.append((profile_name, profile_file, sessions_dir))
            
        elif entry.is_dir():
            profile_json = os.path.join(entry.path, "profile.json")
            if os.path.exists(profile_json):
                profile_file = f"{entry.name}/profile.json"
                profile_name = entry.name
                sessions_dir = os.path.join(entry.path, "sessions")
                profile_targets.append((profile_name, profile_file, sessions_dir))
                
    for profile_name, profile_file, sessions_dir in profile_targets:
        if os.path.exists(sessions_dir) and os.path.isdir(sessions_dir):
            for f_entry in os.scandir(sessions_dir):
                if f_entry.is_file() and f_entry.name.endswith("_history.json"):
                    session_name = f_entry.name.replace("_history.json", "")
                    
                    # Load last_interaction metadata from file
                    last_interaction = None
                    try:
                        with open(f_entry.path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            time_str = data.get("metadata", {}).get("last_interaction")
                            if time_str:
                                last_interaction = datetime.strptime(time_str, "%Y-%m-%d | %H:%M:%S")
                    except Exception:
                        pass
                        
                    # Fallback to file modification time if parsing failed or metadata not present
                    if not last_interaction:
                        try:
                            last_interaction = datetime.fromtimestamp(os.path.getmtime(f_entry.path))
                        except Exception:
                            last_interaction = datetime.min
                            
                    # Clean up profile name for display
                    import re
                    display_name = re.sub(r'_[a-f0-9]{8}$', '', profile_name, flags=re.IGNORECASE)
                    display_name = display_name.replace("_", " ").title()
                    
                    sessions.append({
                        "profile_name": display_name,
                        "session_name": session_name,
                        "last_interaction": last_interaction,
                        "profile_file": profile_file
                    })
                        
    # Sort sessions by last_interaction descending
    sessions.sort(key=lambda x: x["last_interaction"], reverse=True)
    return sessions


class RecentSessionsScreen(ModalScreen):
    """Modal screen for selecting a session from all recent sessions across all profiles."""

    DEFAULT_CSS = """
    RecentSessionsScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #recent_sessions_container {
        width: 80;
        height: 24;
        border: thick $primary;
        background: $panel;
        padding: 1;
        layout: vertical;
    }

    #recent_sessions_title {
        color: $accent;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #recent_sessions_list {
        height: 1fr;
        border: solid $primary;
        margin-bottom: 1;
    }

    #recent_sessions_actions {
        layout: horizontal;
        height: 3;
        width: 100%;
        align: center middle;
    }

    #recent_sessions_actions Button {
        width: 1fr;
        min-width: 8;
        margin: 0 1;
        padding: 0;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "load_session", "Load"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sessions = []

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Select from Recent Sessions", id="recent_sessions_title"),
            OptionList(id="recent_sessions_list"),
            Horizontal(
                Button("Load", id="btn_load", variant="primary"),
                Button("Cancel", id="btn_cancel", variant="error"),
                id="recent_sessions_actions",
            ),
            id="recent_sessions_container",
        )

    def on_mount(self) -> None:
        self.refresh_sessions()

    def format_relative_time(self, dt: datetime) -> str:
        if dt == datetime.min:
            return "never"
        now = datetime.now()
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 0:
            return "just now"
        if seconds < 60:
            return "just now"
        minutes = seconds / 60
        if minutes < 60:
            return f"{int(minutes)}m ago"
        hours = minutes / 60
        if hours < 24:
            return f"{int(hours)}h ago"
        days = hours / 24
        return f"{int(days)}d ago"

    def refresh_sessions(self) -> None:
        """Scan folders for session files and populate OptionList."""
        option_list = self.query_one("#recent_sessions_list", OptionList)
        option_list.clear_options()

        self.sessions = get_all_recent_sessions()

        if not self.sessions:
            option_list.add_option(Option("No recent sessions found.", id="none", disabled=True))
            return

        for idx, s in enumerate(self.sessions):
            profile = s["profile_name"]
            session = s["session_name"]
            rel_time = self.format_relative_time(s["last_interaction"])
            
            # Format: profile_name/session_name (relative time)
            display = f"[bold]{profile}[/bold]/{session} [dim]({rel_time})[/dim]"
            option_list.add_option(Option(display, id=str(idx)))

        if self.sessions:
            option_list.highlighted = 0

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.action_cancel()
        elif event.button.id == "btn_load":
            self.action_load_session()

    def action_load_session(self) -> None:
        option_list = self.query_one("#recent_sessions_list", OptionList)
        if option_list.highlighted is None or not self.sessions:
            return
            
        selected_idx_str = option_list.get_option_at_index(option_list.highlighted).id
        if selected_idx_str == "none":
            return
            
        selected_idx = int(selected_idx_str)
        s = self.sessions[selected_idx]
        
        # Return character file name and session_name
        self.dismiss({
            "character": s["profile_file"],
            "session_name": s["session_name"]
        })
