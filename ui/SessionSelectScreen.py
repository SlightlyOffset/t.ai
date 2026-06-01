import os
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Input, Button, OptionList
from textual.widgets.option_list import Option
from engines.config import get_setting, update_setting
from engines.memory_v2 import memory_manager
from engines.utilities import sanitize_profile_name

class SessionSelectScreen(ModalScreen):
    """Modal screen for managing conversation sessions (load, new, branch, rename, delete)."""

    DEFAULT_CSS = """
    SessionSelectScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #session_container {
        width: 80;
        height: 32;
        border: thick $primary;
        background: $panel;
        padding: 1;
        layout: vertical;
    }

    #session_title {
        color: $accent;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #session_list {
        height: 1fr;
        border: solid $primary;
        margin-bottom: 1;
    }

    .session_input_row {
        layout: horizontal;
        height: auto;
        width: 100%;
        margin-bottom: 1;
        align: left middle;
    }

    .session_input_label {
        width: 24;
        color: $text;
    }

    .session_input_widget {
        width: 1fr;
    }

    #session_error {
        color: $error;
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        display: none;
    }

    #session_actions {
        layout: horizontal;
        height: 3;
        width: 100%;
        align: center middle;
    }

    #session_actions Button {
        width: 1fr;
        min-width: 8;
        margin: 0 1 0 0;
        padding: 0;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+n", "new_session", "New"),
        ("ctrl+b", "branch_session", "Branch"),
        ("ctrl+r", "rename_session", "Rename"),
        ("ctrl+d", "delete_session", "Delete"),
        ("enter", "load_session", "Load"),
    ]

    def __init__(self, character_name: str, **kwargs):
        super().__init__(**kwargs)
        self.character_name = character_name
        self.char_dir = os.path.join("history", sanitize_profile_name(character_name))

    def compose(self) -> ComposeResult:
        yield Container(
            Label(f"Session Manager for {self.character_name.upper()}", id="session_title"),
            Label("", id="session_error"),
            OptionList(id="session_list"),
            Horizontal(
                Label("Session Name:", classes="session_input_label"),
                Input(placeholder="Enter name for new/rename/branch", id="txt_session_name", classes="session_input_widget"),
                classes="session_input_row"
            ),
            Horizontal(
                Label("Branch From Msg #:", classes="session_input_label"),
                Input(placeholder="Optional message number to branch from", id="txt_branch_index", classes="session_input_widget"),
                classes="session_input_row"
            ),
            Horizontal(
                Button("Load", id="btn_load", variant="primary"),
                Button("New", id="btn_new", variant="success"),
                Button("Branch", id="btn_branch", variant="default"),
                Button("Rename", id="btn_rename", variant="default"),
                Button("Delete", id="btn_delete", variant="error"),
                Button("Cancel", id="btn_cancel", variant="error"),
                id="session_actions"
            ),
            id="session_container"
        )

    def on_mount(self) -> None:
        self.refresh_sessions()

    def refresh_sessions(self) -> None:
        """Scan folder for session files and repopulate OptionList."""
        option_list = self.query_one("#session_list", OptionList)
        option_list.clear_options()

        if not os.path.exists(self.char_dir):
            os.makedirs(self.char_dir)

        files = [f for f in os.listdir(self.char_dir) if f.endswith("_history.json")]
        if not files:
            files = ["default_history.json"]

        active_session = get_setting("current_history_session", "default")
        
        selected_index = 0
        for idx, f in enumerate(sorted(files)):
            sname = f.replace("_history.json", "")
            display = f"{sname} (active)" if sname == active_session else sname
            option_list.add_option(Option(display, id=sname))
            if sname == active_session:
                selected_index = idx

        if files:
            option_list.highlighted = selected_index

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Pre-populate the session name text box with the highlighted option's ID."""
        if event.option:
            self.query_one("#txt_session_name", Input).value = event.option.id

    def show_error(self, message: str) -> None:
        err_lbl = self.query_one("#session_error", Label)
        err_lbl.update(message)
        err_lbl.display = True

    def hide_error(self) -> None:
        self.query_one("#session_error", Label).display = False

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.action_cancel()
        elif event.button.id == "btn_load":
            self.action_load_session()
        elif event.button.id == "btn_new":
            self.action_new_session()
        elif event.button.id == "btn_branch":
            self.action_branch_session()
        elif event.button.id == "btn_rename":
            self.action_rename_session()
        elif event.button.id == "btn_delete":
            self.action_delete_session()

    def action_load_session(self) -> None:
        option_list = self.query_one("#session_list", OptionList)
        if option_list.highlighted is None:
            self.show_error("No session selected to load.")
            return

        selected_option = option_list.get_option_at_index(option_list.highlighted)
        session_name = selected_option.id
        
        session_file = os.path.join(self.char_dir, f"{session_name}_history.json")
        if not os.path.exists(session_file):
            self.show_error(f"Session '{session_name}' file not found.")
            return

        update_setting("current_history_session", session_name)
        self.dismiss({"action": "load", "session_name": session_name})

    def action_new_session(self) -> None:
        name_input = self.query_one("#txt_session_name", Input).value.strip()
        name = sanitize_profile_name(name_input)
        if not name:
            self.show_error("Invalid or empty session name.")
            return

        # Write empty history
        memory_manager.save_history(self.character_name, [], session_name=name)
        update_setting("current_history_session", name)
        self.dismiss({"action": "new", "session_name": name})

    def action_branch_session(self) -> None:
        option_list = self.query_one("#session_list", OptionList)
        if option_list.highlighted is None:
            self.show_error("No session selected to branch from.")
            return

        source_option = option_list.get_option_at_index(option_list.highlighted)
        source_name = source_option.id

        new_name_input = self.query_one("#txt_session_name", Input).value.strip()
        new_name = sanitize_profile_name(new_name_input)
        if not new_name:
            self.show_error("Invalid or empty target session name.")
            return

        if new_name == source_name:
            self.show_error("Target session name must be different from source.")
            return

        branch_index_input = self.query_one("#txt_branch_index", Input).value.strip()
        msg_index = None
        if branch_index_input:
            try:
                msg_index = int(branch_index_input)
                if msg_index < 0:
                    raise ValueError()
            except ValueError:
                self.show_error("Branch message index must be a non-negative integer.")
                return

        # Load source data
        current_data = memory_manager.get_full_data(self.character_name, session_name=source_name)
        history = current_data.get("history", [])
        metadata = current_data.get("metadata", {}).copy()

        if msg_index is not None:
            keep_count = max(0, min(len(history), msg_index))
            removed_count = len(history) - keep_count
            old_last_summarized = int(metadata.get("last_summarized_index", 0) or 0)
            if removed_count >= memory_manager.REWIND_MEMORY_CORE_RESET_THRESHOLD or keep_count < old_last_summarized:
                metadata["memory_core"] = ""
                metadata["last_summarized_index"] = 0
            else:
                metadata["last_summarized_index"] = min(old_last_summarized, keep_count)
            history = history[:keep_count]

        # Save new branched history
        memory_manager.save_history(
            self.character_name,
            history,
            relationship_score=metadata.get("relationship_score", 0),
            current_scene=metadata.get("current_scene", "Unknown Location"),
            memory_core=metadata.get("memory_core", ""),
            last_summarized_index=metadata.get("last_summarized_index", 0),
            session_name=new_name
        )

        update_setting("current_history_session", new_name)
        self.dismiss({"action": "branch", "session_name": new_name})

    def action_rename_session(self) -> None:
        option_list = self.query_one("#session_list", OptionList)
        if option_list.highlighted is None:
            self.show_error("No session selected to rename.")
            return

        source_option = option_list.get_option_at_index(option_list.highlighted)
        old_name = source_option.id

        new_name_input = self.query_one("#txt_session_name", Input).value.strip()
        new_name = sanitize_profile_name(new_name_input)
        if not new_name:
            self.show_error("Invalid or empty target session name.")
            return

        if old_name == new_name:
            self.hide_error()
            return

        old_file = os.path.join(self.char_dir, f"{old_name}_history.json")
        new_file = os.path.join(self.char_dir, f"{new_name}_history.json")

        if not os.path.exists(old_file):
            self.show_error(f"Session '{old_name}' file not found.")
            return

        if os.path.exists(new_file):
            self.show_error(f"Session '{new_name}' already exists.")
            return

        try:
            os.rename(old_file, new_file)
            old_bak = old_file + ".bak"
            if os.path.exists(old_bak):
                os.rename(old_bak, new_file + ".bak")

            active_session = get_setting("current_history_session", "default")
            if old_name == active_session:
                update_setting("current_history_session", new_name)
                self.dismiss({"action": "rename", "session_name": new_name})
            else:
                self.refresh_sessions()
                self.hide_error()
        except Exception as e:
            self.show_error(f"Rename failed: {e}")

    def action_delete_session(self) -> None:
        option_list = self.query_one("#session_list", OptionList)
        if option_list.highlighted is None:
            self.show_error("No session selected to delete.")
            return

        target_option = option_list.get_option_at_index(option_list.highlighted)
        name = target_option.id

        active_session = get_setting("current_history_session", "default")
        if name == active_session:
            self.show_error("Cannot delete the active session. Switch sessions first.")
            return

        session_file = os.path.join(self.char_dir, f"{name}_history.json")
        if not os.path.exists(session_file):
            self.show_error(f"Session '{name}' file not found.")
            return

        try:
            os.remove(session_file)
            bak_file = session_file + ".bak"
            if os.path.exists(bak_file):
                os.remove(bak_file)
            self.refresh_sessions()
            self.hide_error()
        except Exception as e:
            self.show_error(f"Delete failed: {e}")
