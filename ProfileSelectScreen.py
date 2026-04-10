import os

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Header, Label, Footer, OptionList
from textual.widgets.option_list import Option

class ProfileSelect(Screen):
    """Screen for selecting character and user profiles."""
    PROFILES_DIR = "profiles"
    USER_PROFILES_DIR = "user_profiles"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="selection_container"):
            yield Vertical(
                Label("Welcome to [bold magenta]t.ai[/bold magenta]", id="welcome_label"),
                Label("Select a Companion Profile:", id="selection_label"),
                OptionList(id="profile_list"),
                id="selection_panel"
            )
        yield Footer()

    def on_mount(self) -> None:
        """Load available character profiles and display them."""
        self.load_character_profiles()

    def load_character_profiles(self) -> None:
        """Populate the OptionList with character profiles."""
        option_list = self.query_one("#profile_list", OptionList)
        option_list.clear_options()
        
        self.query_one("#selection_label").update("Select a Companion Profile:")

        if os.path.exists(self.PROFILES_DIR):
            profiles = [f for f in os.listdir(self.PROFILES_DIR) if f.endswith(".json")]
            for profile in profiles:
                display_name = profile.replace(".json", "").replace("_", " ").title()
                option_list.add_option(Option(display_name, id=profile))
        
        # Track state: choosing character or user
        self.choosing_character = True
        self.selected_character = None

    def load_user_profiles(self) -> None:
        """Populate the OptionList with user profiles."""
        option_list = self.query_one("#profile_list", OptionList)
        option_list.clear_options()
        
        self.query_one("#selection_label").update("Select a User Profile:")

        if os.path.exists(self.USER_PROFILES_DIR):
            profiles = [f for f in os.listdir(self.USER_PROFILES_DIR) if f.endswith(".json")]
            for profile in profiles:
                display_name = profile.replace(".json", "").replace("_", " ").title()
                option_list.add_option(Option(display_name, id=profile))
        
        self.choosing_character = False

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle selection of a profile."""
        if self.choosing_character:
            self.selected_character = event.option.id
            self.load_user_profiles()
        else:
            selected_user = event.option.id
            # Return selection to the app
            self.dismiss({
                "character": self.selected_character,
                "user": selected_user
            })
