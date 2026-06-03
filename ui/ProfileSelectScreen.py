import os
import json

from textual.app import ComposeResult
from textual.containers import Container, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Header, Label, Footer, OptionList
from textual.widgets.option_list import Option
from textual import work

# Import config helper to resolve image protocol settings
from engines.config import get_setting

# Try importing image widgets
try:
    from textual_image.widget import Image, SixelImage, TGPImage, HalfcellImage
    HAS_TEXTUAL_IMAGE = True
except ImportError:
    HAS_TEXTUAL_IMAGE = False

class ProfileSelect(Screen):
    """Screen for selecting character and user profiles with a split-pane card layout."""
    PROFILES_DIR = "profiles"
    USER_PROFILES_DIR = "user_profiles"

    DEFAULT_CSS = """
    #split_container {
        layout: horizontal;
        height: 1fr;
        width: 100%;
    }
    #selection_panel {
        width: 40;
        height: 100%;
        background: $panel;
        border-right: tall $accent;
        padding: 1;
    }
    #preview_panel {
        width: 1fr;
        height: 100%;
        padding: 2;
        background: $surface;
    }
    #preview_title {
        color: $accent;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-top: 0;
        margin-bottom: 1;
    }
    .avatar_container {
        width: 100%;
        height: auto;
        align: center middle;
        margin-bottom: 1;
    }
    #preview_avatar {
        width: 32;
        height: 16;
        border: solid $accent;
        display: block;
        margin-bottom: 1;
    }
    #preview_name {
        text-align: center;
        width: 100%;
        text-style: bold;
        margin-bottom: 1;
    }
    #preview_stats {
        text-align: center;
        width: 100%;
        color: $text-disabled;
        margin-bottom: 1;
    }
    #preview_personality {
        margin-bottom: 1;
        width: 100%;
    }
    #preview_likes_dislikes {
        margin-bottom: 1;
        width: 100%;
    }
    #preview_appearance {
        margin-bottom: 1;
        width: 100%;
    }
    #preview_backstory {
        margin-bottom: 1;
        width: 100%;
    }
    """

    def __init__(self, choose_user_only: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.choose_user_only = choose_user_only
        self.selected_character = None
        self.choosing_character = not choose_user_only
        self.current_preview_file = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="split_container"):
            with Vertical(id="selection_panel"):
                yield Label("Welcome to [bold magenta]t.ai[/bold magenta]", id="welcome_label")
                yield Label("Select a Companion Profile:", id="selection_label")
                yield OptionList(id="profile_list")
            with ScrollableContainer(id="preview_panel"):
                yield Label("--- Profile Preview ---", id="preview_title")
                with Vertical(id="preview_avatar_wrap", classes="avatar_container"):
                    # Avatar will be dynamically mounted here
                    pass
                yield Label("", id="preview_name")
                yield Label("", id="preview_stats")
                yield Label("", id="preview_personality")
                yield Label("", id="preview_likes_dislikes")
                yield Label("", id="preview_appearance")
                yield Label("", id="preview_backstory")
        yield Footer()

    def on_mount(self) -> None:
        """Load available profiles, display them, and focus the list."""
        if self.choose_user_only:
            self.load_user_profiles()
        else:
            self.load_character_profiles()
            
        try:
            self.query_one("#profile_list", OptionList).focus()
        except Exception:
            pass

    def load_character_profiles(self) -> None:
        """Populate the OptionList with character profiles."""
        option_list = self.query_one("#profile_list", OptionList)
        option_list.clear_options()
        
        self.query_one("#selection_label").update("Select a Companion Profile:")
        self.choosing_character = True
        self.selected_character = None

        profiles = []
        if os.path.exists(self.PROFILES_DIR):
            profiles = [f for f in os.listdir(self.PROFILES_DIR) if f.endswith(".json")]
            profiles.sort()
            for profile in profiles:
                display_name = profile.replace(".json", "").replace("_", " ").title()
                option_list.add_option(Option(display_name, id=profile))
        
        # Check option count safely to avoid TypeError with MagicMocks in unit tests
        count = option_list.option_count
        if isinstance(count, int) and count > 0:
            first_opt = option_list.get_option_at_index(0)
            if first_opt and first_opt.id:
                self.update_preview(first_opt.id)
        else:
            self.clear_preview()

    def load_user_profiles(self) -> None:
        """Populate the OptionList with user profiles."""
        option_list = self.query_one("#profile_list", OptionList)
        option_list.clear_options()
        
        self.query_one("#selection_label").update("Select a User Profile:")
        self.choosing_character = False

        profiles = []
        if os.path.exists(self.USER_PROFILES_DIR):
            profiles = [f for f in os.listdir(self.USER_PROFILES_DIR) if f.endswith(".json")]
            profiles.sort()
            for profile in profiles:
                display_name = profile.replace(".json", "").replace("_", " ").title()
                option_list.add_option(Option(display_name, id=profile))
        
        # Check option count safely to avoid TypeError with MagicMocks in unit tests
        count = option_list.option_count
        if isinstance(count, int) and count > 0:
            first_opt = option_list.get_option_at_index(0)
            if first_opt and first_opt.id:
                self.update_preview(first_opt.id)
        else:
            self.clear_preview()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Handle highlight changes in the OptionList to update the preview pane."""
        if event.option is None or event.option.id is None:
            self.clear_preview()
            return
        
        self.update_preview(event.option.id)

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

    def update_preview(self, profile_file: str) -> None:
        """Load profile file and update details / trigger background avatar loading."""
        self.current_preview_file = profile_file
        dir_path = self.PROFILES_DIR if self.choosing_character else self.USER_PROFILES_DIR
        full_path = os.path.join(dir_path, profile_file)
        
        if not os.path.exists(full_path):
            self.clear_preview()
            return
            
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                profile_data = json.load(f)
        except Exception:
            self.clear_preview()
            return
            
        # Update text details
        self.update_preview_details(profile_data)
        
        # Optimize and update avatar in background
        avatar_path = profile_data.get("avatar_path")
        if avatar_path:
            self._load_and_optimize_avatar(profile_file, avatar_path)
        else:
            self._mount_preview_avatar(None)

    def update_preview_details(self, data: dict) -> None:
        """Update the preview card labels with the highlighted profile data."""
        name = data.get("name", "Unknown")
        personality = data.get("personality_type", "Unknown")
        backstory = data.get("backstory", "No backstory available.")
        
        # Color profile name based on colors in JSON if available
        colors = data.get("colors", {})
        name_color = colors.get("name_lbl", "magenta" if self.choosing_character else "cyan")
        
        # Display name, including alt names if character
        alt_names = data.get("alt_names", "")
        if alt_names:
            self.query_one("#preview_name", Label).update(f"[bold {name_color}]{name}[/bold {name_color}] [dim]({alt_names})[/dim]")
        else:
            self.query_one("#preview_name", Label).update(f"[bold {name_color}]{name}[/bold {name_color}]")
        
        # Stats
        char_info = data.get("character_info", {})
        gender = data.get("gender") or char_info.get("gender") or "Unknown"
        
        if self.choosing_character:
            age = char_info.get("age") or "Unknown"
            stats_text = f"[bold]Gender:[/bold] {gender}   |   [bold]Age:[/bold] {age}"
        else:
            height = char_info.get("height") or "Unknown"
            stats_text = f"[bold]Gender:[/bold] {gender}   |   [bold]Height:[/bold] {height}"
            
        self.query_one("#preview_stats", Label).update(stats_text)
        
        # Personality
        self.query_one("#preview_personality", Label).update(f"[bold]Personality:[/bold] [italic]{personality}[/italic]")
        
        # Likes and Dislikes
        likes = char_info.get("likes", [])
        dislikes = char_info.get("dislikes", [])
        likes_str = ", ".join(likes) if likes else "None"
        dislikes_str = ", ".join(dislikes) if dislikes else "None"
        
        likes_dislikes_text = (
            f"[bold green]Likes:[/bold green] {likes_str}\n"
            f"[bold red]Dislikes:[/bold red] {dislikes_str}"
        )
        self.query_one("#preview_likes_dislikes", Label).update(likes_dislikes_text)
        
        # Appearance
        appearance = char_info.get("appearance", "")
        appearance_widget = self.query_one("#preview_appearance", Label)
        if appearance:
            appearance_widget.update(f"[bold]Appearance:[/bold]\n{appearance}")
            appearance_widget.display = True
        else:
            appearance_widget.display = False
            
        # Backstory
        self.query_one("#preview_backstory", Label).update(f"[bold]Backstory:[/bold]\n{backstory}")

    def clear_preview(self) -> None:
        """Clear all preview card widgets."""
        self.current_preview_file = None
        try:
            self.query_one("#preview_name", Label).update("")
            self.query_one("#preview_stats", Label).update("")
            self.query_one("#preview_personality", Label).update("")
            self.query_one("#preview_likes_dislikes", Label).update("")
            self.query_one("#preview_appearance", Label).display = False
            self.query_one("#preview_backstory", Label).update("")
            self._mount_preview_avatar(None)
        except Exception:
            pass

    def _resolve_image_widget_type(self) -> type | None:
        """Resolve the configured terminal image widget class."""
        if not HAS_TEXTUAL_IMAGE:
            return None
        protocol = get_setting("image_protocol", "auto")
        if protocol == "none":
            return None
        if protocol == "kitty":
            return TGPImage
        if protocol == "sixel":
            return SixelImage
        if protocol == "blocky":
            return HalfcellImage
        return Image

    def _mount_preview_avatar(self, image_path: str | None) -> None:
        """Mount or update the avatar image widget in the preview card."""
        try:
            container = self.query_one("#preview_avatar_wrap", Vertical)
        except Exception:
            return

        desired_widget_type = self._resolve_image_widget_type() or Static
        widget_id = "preview_avatar"
        
        try:
            existing = self.query_one(f"#{widget_id}")
        except Exception:
            existing = None

        if existing is not None:
            # If the widget class matches and it's not a fallback Static, update the image property
            if type(existing) is desired_widget_type and desired_widget_type is not Static:
                try:
                    existing.image = image_path
                    return
                except Exception:
                    pass
            # Otherwise, remove and recreate
            existing.remove()
            self.call_after_refresh(self._mount_preview_avatar, image_path)
            return

        # Create new widget
        if desired_widget_type is Static or not image_path:
            container.mount(Static("🖼️", id=widget_id))
        else:
            try:
                container.mount(desired_widget_type(image_path, id=widget_id))
            except Exception:
                container.mount(Static("🖼️", id=widget_id))

    @work(thread=True)
    def _load_and_optimize_avatar(self, profile_file: str, avatar_path: str) -> None:
        """Asynchronously load and optimize the avatar image in a background thread."""
        from engines.image_optimizer import get_or_create_optimized_image
        optimized_path = get_or_create_optimized_image(avatar_path, max_dim=500)
        
        def update_ui():
            # Check for race conditions
            if self.current_preview_file != profile_file:
                return
            path_to_use = optimized_path if optimized_path and os.path.exists(optimized_path) else None
            self._mount_preview_avatar(path_to_use)
            
        if hasattr(self, "app") and self.app is not None and hasattr(self.app, "call_from_thread"):
            self.app.call_from_thread(update_ui)
        else:
            update_ui()
