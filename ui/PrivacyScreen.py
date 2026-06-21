from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Label

class PrivacyScreen(Screen):
    """Semi-transparent overlay lock screen triggered by inactivity."""

    DEFAULT_CSS = """
    PrivacyScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.9);
    }
    
    #privacy_container {
        width: 60;
        height: 15;
        border: thick $accent;
        background: $panel;
        padding: 2;
        align: center middle;
        layout: vertical;
    }
    
    #privacy_lock_icon {
        color: $accent;
        margin-bottom: 1;
        text-align: center;
        width: 100%;
    }
    
    #privacy_title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
        text-align: center;
        width: 100%;
    }
    
    #privacy_message {
        color: $text;
        text-align: center;
        margin-bottom: 2;
        width: 100%;
    }
    
    #privacy_hint {
        color: $text-disabled;
        text-style: italic;
        text-align: center;
        width: 100%;
    }
    """

    BINDINGS = [
        ("enter", "unlock", "Unlock"),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Label("🔒", id="privacy_lock_icon"),
            Label("Session Locked", id="privacy_title"),
            Label("This session was locked due to inactivity.", id="privacy_message"),
            Label("Press [Enter] to resume chat", id="privacy_hint"),
            id="privacy_container"
        )

    def action_unlock(self) -> None:
        self.dismiss(True)
