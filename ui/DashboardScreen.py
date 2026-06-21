import os
import random
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Header, Label, Footer, Button
from ui.RecentSessionsScreen import get_all_recent_sessions, RecentSessionsScreen


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
        width: 80;
        height: auto;
        border: thick $primary;
        background: $panel;
        padding: 2;
    }

    #dashboard_ascii {
        width: 100%;
        text-align: center;
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }

    #dashboard_tagline {
        width: 100%;
        text-align: center;
        color: $text-disabled;
        text-style: italic;
        margin-bottom: 2;
    }

    #dashboard_menu {
        align: center middle;
        layout: vertical;
        width: auto;
        height: auto;
    }

    .dashboard_btn {
        background: transparent;
        border: none;
        color: $text;
        text-align: left;
        width: 32;
        height: 1;
        margin: 0 0 1 0;
        padding: 0;
        min-width: 8;
    }

    .dashboard_btn:hover {
        color: $accent;
        text-style: bold;
        background: transparent;
    }

    .dashboard_btn:focus {
        color: $accent;
        text-style: bold;
        background: transparent;
    }
    """

    BINDINGS = [
        ("c", "choose_companion", "Choose Companion"),
        ("s", "recent_sessions", "Recent Sessions"),
        ("p", "open_settings", "Settings"),
        ("q", "quit_app", "Quit"),
        ("escape", "cancel", "Cancel"),
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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="dashboard_container"):
            yield Label(self.ASCII_ART, id="dashboard_ascii")
            tagline = random.choice(self.TAGLINES)
            yield Label(tagline, id="dashboard_tagline")
            with Vertical(id="dashboard_menu"):
                yield Button("[c] Choose Companion", id="btn_choose_companion", classes="dashboard_btn")
                
                # Show recent sessions button if any exist in the system
                if len(get_all_recent_sessions()) > 0:
                    yield Button("[s] Recent Sessions", id="btn_recent_sessions", classes="dashboard_btn")
                    
                yield Button("[p] Settings", id="btn_settings", classes="dashboard_btn")
                yield Button("[q] Quit", id="btn_quit", classes="dashboard_btn")
        yield Footer()

    def action_choose_companion(self) -> None:
        from ui.ProfileSelectScreen import ProfileSelect
        self.push_screen(ProfileSelect(), callback=self.on_profile_selected)

    def action_recent_sessions(self) -> None:
        if len(get_all_recent_sessions()) == 0:
            self.notify("No recent sessions found.", severity="error")
            return
        self.push_screen(RecentSessionsScreen(), callback=self.on_session_selected)

    def action_open_settings(self) -> None:
        from ui.SettingsScreen import SettingsScreen
        self.push_screen(SettingsScreen(), callback=self.on_settings_saved)

    def action_quit_app(self) -> None:
        self.app.action_quit()

    def action_cancel(self) -> None:
        if self.app.char_path:
            self.dismiss(None)
        else:
            self.notify("No active profile loaded. Please choose a companion first.", severity="error")

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
