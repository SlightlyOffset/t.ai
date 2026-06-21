import os
import random
import requests
import asyncio
from textual import work
from textual.binding import Binding
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Label, Button
from ui.RecentSessionsScreen import get_all_recent_sessions, RecentSessionsScreen
from engines.config import get_setting


class DashboardScreen(Screen):
    """A keyboard-centric startup dashboard splash screen inspired by alpha-nvim."""

    DEFAULT_CSS = """
    DashboardScreen {
        align: center middle;
        background: $surface;
    }

    #dashboard_container {
        align: center middle;
        layout: vertical;
        width: 100%;
        height: 100%;
        background: $surface;
    }

    #dashboard_ascii {
        width: 100%;
        text-align: center;
        color: $accent;
        text-style: bold;
        margin-bottom: 2;
    }

    #dashboard_tagline {
        width: 100%;
        text-align: center;
        color: $text-disabled;
        text-style: italic;
        margin-bottom: 2;
    }

    #dashboard_menu {
        width: 100%;
        align: center middle;
        layout: vertical;
        height: auto;
    }

    Button.dashboard_btn,
    Button.dashboard_btn:hover,
    Button.dashboard_btn:focus {
        background: transparent;
        border: none;
        width: 40;
        height: 1;
        margin: 0 0 1 0;
    }

    Button.dashboard_btn {
        color: $text;
    }

    Button.dashboard_btn:hover,
    Button.dashboard_btn:focus {
        color: $accent;
        text-style: bold;
    }

    .dashboard_separator {
        color: $text-disabled;
        opacity: 0.3;
        width: 100%;
        text-align: center;
        margin-top: 1;
        margin-bottom: 1;
    }

    #dashboard_recent_title {
        color: $accent;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #stats_label {
        width: 100%;
        text-align: center;
        color: $text-disabled;
        margin-top: 1;
        margin-bottom: 1;
    }

    #dashboard_tip {
        width: 100%;
        text-align: center;
        color: $text-disabled;
        text-style: italic;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("c", "choose_companion", "Choose Companion"),
        ("s", "recent_sessions", "Recent Sessions"),
        ("p", "open_settings", "Settings"),
        ("q", "quit_app", "Quit"),
        ("escape", "cancel", "Cancel"),
        Binding("1", "load_recent_1", "Resume Session 1", show=False),
        Binding("2", "load_recent_2", "Resume Session 2", show=False),
        Binding("3", "load_recent_3", "Resume Session 3", show=False),
    ]

    ASCII_ART = (
        "  ██╗                     ██╗\n"
        "██████╗          █████╗   ╚═╝\n"
        "  ██║            ██╔══██╗ ██╗\n"
        "  ██║     ██╗    ███████║ ██║\n"
        "  ╚██╗    ╚═╝    ██╔══██║ ██║\n"
        "   ╚═╝           ╚═╝  ╚═╝ ╚═╝"
    )

    TAGLINES = [
        "Your terminal companion, always ready.",
        "Synthesizing thoughts, one byte at a time.",
        "Connecting to local thoughts...",
        "A local mind waiting to converse.",
        "Ready when you are, Captain.",
        "A companion that lives in the command line.",
        "Zero-latency friendship starts here.",
        "Hello again! What shall we build today?"
    ]

    TIPS = [
        "Press Ctrl+g at any time to return to this dashboard.",
        "Use //recap to get a summary of your recent conversations.",
        "Double click or press Enter on a companion profile to load it.",
        "Use //import_card to import SillyTavern character cards directly.",
        "You can configure the inactivity timeout for this dashboard in Settings.",
        "Press Alt+Right Arrow to regenerate the last companion response.",
        "Press Ctrl+b to toggle the status and relationship sidebar.",
        "Type //help in chat to see all available slash commands.",
        "Use //branch to create a new branch from your active chat session."
    ]

    def compose(self) -> ComposeResult:
        with Container(id="dashboard_container"):
            yield Label(self.ASCII_ART, id="dashboard_ascii")
            tagline = random.choice(self.TAGLINES)
            yield Label(tagline, id="dashboard_tagline")
            with Vertical(id="dashboard_menu"):
                yield Button(r"\[c] Choose Companion", id="btn_choose_companion", classes="dashboard_btn")
                
                # Show recent sessions button if any exist in the system
                if len(get_all_recent_sessions()) > 0:
                    yield Button(r"\[s] Recent Sessions", id="btn_recent_sessions", classes="dashboard_btn")
                    
                yield Button(r"\[p] Settings", id="btn_settings", classes="dashboard_btn")
                yield Button(r"\[q] Quit", id="btn_quit", classes="dashboard_btn")

            # Resume Recent Conversations (top 3)
            recent_sessions = get_all_recent_sessions()[:3]
            if recent_sessions:
                yield Label("─" * 40, classes="dashboard_separator")
                yield Label("Resume Recent Conversations:", id="dashboard_recent_title")
                for idx, s in enumerate(recent_sessions):
                    profile = s["profile_name"]
                    session = s["session_name"]
                    label = f"\\[{idx + 1}] {profile}/{session}"
                    yield Button(label, id=f"btn_recent_{idx + 1}", classes="dashboard_btn")

            # Separator, Stats Panel and Tip of the Day
            yield Label("─" * 40, classes="dashboard_separator")
            yield Label("Loading system and LLM status...", id="stats_label")
            tip_text = f"Tip: {random.choice(self.TIPS)}"
            yield Label(tip_text, id="dashboard_tip")

    def on_mount(self) -> None:
        self.update_stats_async()

    def get_companions_count(self) -> int:
        profiles_dir = "profiles"
        if not os.path.exists(profiles_dir):
            return 0
        count = 0
        for entry in os.scandir(profiles_dir):
            if entry.is_file() and entry.name.endswith(".json") and entry.name != "settings.json":
                count += 1
            elif entry.is_dir() and os.path.exists(os.path.join(entry.path, "profile.json")):
                count += 1
        return count

    @work(exclusive=True)
    async def update_stats_async(self) -> None:
        """Fetch system statistics and local LLM connection status asynchronously."""
        comp_count = self.get_companions_count()
        sess_count = len(get_all_recent_sessions())

        # CPU/RAM Metrics
        try:
            cpu, ram = self.app._get_local_metrics()
            metrics_str = f"CPU: {cpu:.0f}% | RAM: {ram:.0f}%"
        except Exception:
            metrics_str = "CPU: --% | RAM: --%"

        # Local LLM Server Check
        llm_url = get_setting("local_llm_url", "http://localhost:11434/v1")
        
        def check_connection():
            try:
                base_url = llm_url.replace("/v1", "").rstrip("/")
                resp = requests.get(base_url, timeout=1.0)
                if resp.status_code == 200:
                    return "Online"
                resp2 = requests.get(llm_url, timeout=1.0)
                if resp2.status_code < 500:
                    return "Online"
            except Exception:
                pass
            return "Offline"

        loop = asyncio.get_event_loop()
        llm_status = await loop.run_in_executor(None, check_connection)

        stats_text = f"Companions: {comp_count} | Sessions: {sess_count} | {metrics_str} | LLM: {llm_status}"
        try:
            self.query_one("#stats_label", Label).update(stats_text)
        except Exception:
            pass

    def action_choose_companion(self) -> None:
        from ui.ProfileSelectScreen import ProfileSelect
        self.app.push_screen(ProfileSelect(), callback=self.on_profile_selected)

    def action_recent_sessions(self) -> None:
        if len(get_all_recent_sessions()) == 0:
            self.notify("No recent sessions found.", severity="error")
            return
        self.app.push_screen(RecentSessionsScreen(), callback=self.on_session_selected)

    def action_open_settings(self) -> None:
        from ui.SettingsScreen import SettingsScreen
        self.app.push_screen(SettingsScreen(), callback=self.on_settings_saved)

    def action_quit_app(self) -> None:
        self.app.action_quit()

    def action_cancel(self) -> None:
        if self.app.char_path:
            self.dismiss(None)
        else:
            self.notify("No active profile loaded. Please choose a companion first.", severity="error")

    def action_load_recent_1(self) -> None:
        self.load_recent_session_by_index(0)

    def action_load_recent_2(self) -> None:
        self.load_recent_session_by_index(1)

    def action_load_recent_3(self) -> None:
        self.load_recent_session_by_index(2)

    def load_recent_session_by_index(self, index: int) -> None:
        sessions = get_all_recent_sessions()
        if index < len(sessions):
            s = sessions[index]
            self.dismiss({
                "character": s["profile_file"],
                "session_name": s["session_name"]
            })

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn_choose_companion":
            self.action_choose_companion()
        elif button_id == "btn_recent_sessions":
            self.action_recent_sessions()
        elif button_id == "btn_settings":
            self.action_open_settings()
        elif button_id == "btn_quit":
            self.action_quit_app()
        elif button_id.startswith("btn_recent_"):
            try:
                idx = int(button_id.split("_")[-1]) - 1
                self.load_recent_session_by_index(idx)
            except Exception:
                pass

    def on_profile_selected(self, result: dict | None) -> None:
        if result:
            self.dismiss(result)

    def on_session_selected(self, result: dict | None) -> None:
        if result:
            self.dismiss(result)

    def on_settings_saved(self, result: dict | None) -> None:
        if result:
            self.app.on_settings_saved(result)
            self.notify("Settings saved.", severity="information")
