from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Label, TabbedContent, TabPane, Switch, Input, Select, Button

class SettingsScreen(ModalScreen):
    """Dedicated settings screen with categorized tabs for configuration."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._plugins_info = self._get_plugin_info()

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #settings_container {
        width: 80;
        height: 32;
        border: thick $primary;
        background: $panel;
        padding: 1;
        layout: vertical;
    }

    #settings_title {
        color: $accent;
        text-style: bold;
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #settings_tabs {
        height: 1fr;
    }

    .settings_pane {
        padding: 1;
    }

    .settings_row {
        layout: horizontal;
        height: auto;
        width: 100%;
        margin-bottom: 1;
        align: left middle;
    }

    .settings_label {
        width: 32;
        color: $text;
    }

    .settings_widget {
        width: 38;
    }

    #settings_error {
        color: $error;
        text-style: bold;
        text-align: center;
        width: 100%;
        margin: 1 0;
        display: none;
    }

    #settings_actions {
        layout: horizontal;
        height: 3;
        width: 100%;
        align: right middle;
        margin-top: 1;
    }

    #settings_actions Button {
        margin-left: 2;
    }

    .plugin_divider {
        width: 100%;
        color: $primary;
        margin: 1 0;
    }

    .settings_note {
        width: 100%;
        margin-bottom: 1;
        padding-left: 2;
        color: $text;
        opacity: 0.6;
        text-style: italic;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+s", "save", "Save"),
    ]

    def compose(self) -> ComposeResult:
        from engines.config import load_settings
        from ui.menu import TaiMenu

        settings = load_settings()

        # Extract values or defaults
        interaction_mode = settings.get("interaction_mode", "rp")
        auto_recap_on_start = settings.get("auto_recap_on_start", False)
        auto_chat_load = settings.get("auto_chat_load", True)
        auto_chat_load_limit = str(settings.get("auto_chat_load_limit", 20))
        scroll_load_limit = str(settings.get("scroll_load_limit", 10))
        smooth_streaming = settings.get("smooth_streaming", True)
        streaming_delay = str(settings.get("streaming_delay", 0.055))
        image_protocol = settings.get("image_protocol", "auto")
        image_size = settings.get("image_size", "medium")
        suppress_errors = settings.get("suppress_errors", True)

        inactivity_dashboard_timeout = str(settings.get("inactivity_dashboard_timeout", 12))
        privacy_screen_timeout = str(settings.get("privacy_screen_timeout", 3))

        default_llm_model = settings.get("default_llm_model", "fluffy/l3-8b-stheno-v3.2")
        summarizer_model = settings.get("summarizer_model", "gemma2:2b")
        local_utility_model = settings.get("local_utility_model", "phi3")
        memory_limit = str(settings.get("memory_limit", 15))
        repetition_penalty = str(settings.get("repetition_penalty", 1.15))
        max_tokens = str(settings.get("max_tokens", 300))
        max_input_tokens = str(settings.get("max_input_tokens", 6200))
        local_llm_keep_alive = str(settings.get("local_llm_keep_alive", "5m"))

        tts_enabled = settings.get("tts_enabled", False)
        character_speak = settings.get("character_speak", True)
        speak_narration = settings.get("speak_narration", True)
        default_tts_engine = settings.get("default_tts_engine", "edge-tts")
        default_tts_voice = settings.get("default_tts_voice", "en-GB-SoniaNeural")
        narration_tts_voice = settings.get("narration_tts_voice", "en-US-AndrewNeural")
        tts_rate = str(settings.get("tts_rate", 170))
        show_tts_engine = settings.get("show_tts_engine", True)
        unload_tts_after_generation = settings.get("unload_tts_after_generation", False)

        remote_llm_url = settings.get("remote_llm_url") or ""
        remote_tts_url = settings.get("remote_tts_url") or ""
        local_llm_url = settings.get("local_llm_url") or ""
        privacy_mode = settings.get("privacy_mode", False)
        mcp_enabled = settings.get("mcp_enabled", False)

        debug_mode = settings.get("debug_mode", False)
        execute_command = settings.get("execute_command", False)
        overhaul_pipeline_enabled = settings.get("overhaul_pipeline_enabled", True)
        overhaul_instrumentation_enabled = settings.get("overhaul_instrumentation_enabled", True)
        overhaul_state_enabled = settings.get("overhaul_state_enabled", True)
        overhaul_memory_enabled = settings.get("overhaul_memory_enabled", True)
        overhaul_planner_enabled = settings.get("overhaul_planner_enabled", True)
        overhaul_candidates_enabled = settings.get("overhaul_candidates_enabled", False)
        overhaul_critic_enabled = settings.get("overhaul_critic_enabled", False)
        overhaul_candidate_count = str(settings.get("overhaul_candidate_count", 2))
        overhaul_style_profile = settings.get("overhaul_style_profile", "balanced")
        
        disabled_plugins = settings.get("disabled_plugins", [])

        with Container(id="settings_container"):
            yield Label("t.ai Global Settings Configuration", id="settings_title")
            yield Label("", id="settings_error")

            with TabbedContent(id="settings_tabs"):
                with TabPane("General", id="tab_general"):
                    with VerticalScroll(classes="settings_pane"):
                        with Horizontal(classes="settings_row"):
                            yield Label("Interaction Mode:", classes="settings_label")
                            yield Select(
                                [("RP Mode", "rp"), ("Casual Mode", "casual")],
                                value=interaction_mode,
                                id="interaction_mode",
                                classes="settings_widget"
                            )
                        with Horizontal(classes="settings_row"):
                            yield Label("Auto Recap on Start:", classes="settings_label")
                            yield Switch(value=auto_recap_on_start, id="auto_recap_on_start", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Auto Chat Load on Start:", classes="settings_label")
                            yield Switch(value=auto_chat_load, id="auto_chat_load", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Initial Chat Load Limit:", classes="settings_label")
                            yield Input(value=auto_chat_load_limit, id="auto_chat_load_limit", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Scroll Load Limit (Step):", classes="settings_label")
                            yield Input(value=scroll_load_limit, id="scroll_load_limit", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Smooth Streaming:", classes="settings_label")
                            yield Switch(value=smooth_streaming, id="smooth_streaming", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Streaming Delay (s):", classes="settings_label")
                            yield Input(value=streaming_delay, id="streaming_delay", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Image Protocol:", classes="settings_label")
                            yield Select(
                                TaiMenu.IMAGE_PROTOCOLS,
                                value=image_protocol,
                                id="image_protocol",
                                classes="settings_widget"
                            )
                        with Horizontal(classes="settings_row"):
                            yield Label("Image Size/Quality:", classes="settings_label")
                            yield Select(
                                [("Small (400px)", "small"), ("Medium (800px)", "medium"), ("Large (1200px)", "large")],
                                value=image_size,
                                id="image_size",
                                classes="settings_widget"
                            )
                        with Horizontal(classes="settings_row"):
                            yield Label("Suppress Errors:", classes="settings_label")
                            yield Switch(value=suppress_errors, id="suppress_errors", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Inactivity Dashboard Timeout (h):", classes="settings_label")
                            yield Input(value=inactivity_dashboard_timeout, id="inactivity_dashboard_timeout", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Inactivity Privacy Timeout (m):", classes="settings_label")
                            yield Input(value=privacy_screen_timeout, id="privacy_screen_timeout", classes="settings_widget")

                with TabPane("AI Engine", id="tab_ai"):
                    with VerticalScroll(classes="settings_pane"):
                        with Horizontal(classes="settings_row"):
                            yield Label("Local LLM API URL:", classes="settings_label")
                            yield Input(value=local_llm_url, id="local_llm_url", classes="settings_widget")
                        yield Label("Note: Single-model backends (like KoboldCPP) ignore the model fields below and use the model loaded in the server.", classes="settings_note")
                        with Horizontal(classes="settings_row"):
                            yield Label("Default LLM Model:", classes="settings_label")
                            yield Input(value=default_llm_model, id="default_llm_model", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Summarizer Model:", classes="settings_label")
                            yield Input(value=summarizer_model, id="summarizer_model", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Local Utility Model:", classes="settings_label")
                            yield Input(value=local_utility_model, id="local_utility_model", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Memory Message Limit:", classes="settings_label")
                            yield Input(value=memory_limit, id="memory_limit", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Repetition Penalty:", classes="settings_label")
                            yield Input(value=repetition_penalty, id="repetition_penalty", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Max Response Tokens:", classes="settings_label")
                            yield Input(value=max_tokens, id="max_tokens", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Max Context Tokens:", classes="settings_label")
                            yield Input(value=max_input_tokens, id="max_input_tokens", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Ollama Keep-Alive:", classes="settings_label")
                            yield Input(value=local_llm_keep_alive, id="local_llm_keep_alive", classes="settings_widget")

                with TabPane("TTS / Audio", id="tab_tts"):
                    with VerticalScroll(classes="settings_pane"):
                        with Horizontal(classes="settings_row"):
                            yield Label("TTS Master Enabled:", classes="settings_label")
                            yield Switch(value=tts_enabled, id="tts_enabled", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Character Speak:", classes="settings_label")
                            yield Switch(value=character_speak, id="character_speak", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Speak Narration:", classes="settings_label")
                            yield Switch(value=speak_narration, id="speak_narration", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Default TTS Engine:", classes="settings_label")
                            yield Select(
                                TaiMenu.TTS_ENGINES,
                                value=default_tts_engine,
                                id="default_tts_engine",
                                classes="settings_widget"
                            )
                        with Horizontal(classes="settings_row"):
                            yield Label("Default TTS Voice:", classes="settings_label")
                            yield Select(
                                TaiMenu.EDGE_VOICES,
                                value=default_tts_voice,
                                id="default_tts_voice",
                                classes="settings_widget"
                            )
                        with Horizontal(classes="settings_row"):
                            yield Label("Narration TTS Voice:", classes="settings_label")
                            yield Select(
                                TaiMenu.EDGE_VOICES,
                                value=narration_tts_voice,
                                id="narration_tts_voice",
                                classes="settings_widget"
                            )
                        with Horizontal(classes="settings_row"):
                            yield Label("TTS Speech Rate:", classes="settings_label")
                            yield Input(value=tts_rate, id="tts_rate", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Show TTS Engine Selector:", classes="settings_label")
                            yield Switch(value=show_tts_engine, id="show_tts_engine", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Auto-Unload Local TTS:", classes="settings_label")
                            yield Switch(value=unload_tts_after_generation, id="unload_tts_after_generation", classes="settings_widget")

                with TabPane("Cloud Tunnel", id="tab_cloud"):
                    with VerticalScroll(classes="settings_pane"):
                        with Horizontal(classes="settings_row"):
                            yield Label("Remote LLM URL:", classes="settings_label")
                            yield Input(value=remote_llm_url, id="remote_llm_url", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Remote TTS URL:", classes="settings_label")
                            yield Input(value=remote_tts_url, id="remote_tts_url", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Privacy Mode (Redact PII):", classes="settings_label")
                            yield Switch(value=privacy_mode, id="privacy_mode", classes="settings_widget")

                with TabPane("Advanced", id="tab_advanced"):
                    with VerticalScroll(classes="settings_pane"):
                        with Horizontal(classes="settings_row"):
                            yield Label("Debug Mode:", classes="settings_label")
                            yield Switch(value=debug_mode, id="debug_mode", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Enable MCP (Tool Calling):", classes="settings_label")
                            yield Switch(value=mcp_enabled, id="mcp_enabled", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Allow Command Execution:", classes="settings_label")
                            yield Switch(value=execute_command, id="execute_command", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Overhaul Pipeline Enabled:", classes="settings_label")
                            yield Switch(value=overhaul_pipeline_enabled, id="overhaul_pipeline_enabled", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Overhaul Instrumentation:", classes="settings_label")
                            yield Switch(value=overhaul_instrumentation_enabled, id="overhaul_instrumentation_enabled", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Overhaul State Tracking:", classes="settings_label")
                            yield Switch(value=overhaul_state_enabled, id="overhaul_state_enabled", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Overhaul Memory Manager:", classes="settings_label")
                            yield Switch(value=overhaul_memory_enabled, id="overhaul_memory_enabled", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Overhaul Planner Engine:", classes="settings_label")
                            yield Switch(value=overhaul_planner_enabled, id="overhaul_planner_enabled", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Overhaul Candidates Enabled:", classes="settings_label")
                            yield Switch(value=overhaul_candidates_enabled, id="overhaul_candidates_enabled", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Overhaul Critic Enabled:", classes="settings_label")
                            yield Switch(value=overhaul_critic_enabled, id="overhaul_critic_enabled", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Overhaul Candidate Count:", classes="settings_label")
                            yield Input(value=overhaul_candidate_count, id="overhaul_candidate_count", classes="settings_widget")
                        with Horizontal(classes="settings_row"):
                            yield Label("Overhaul Style Profile:", classes="settings_label")
                            yield Select(
                                [("Balanced", "balanced"), ("Creative", "creative"), ("Precise", "precise")],
                                value=overhaul_style_profile,
                                id="overhaul_style_profile",
                                classes="settings_widget"
                            )

                with TabPane("Plugins", id="tab_plugins"):
                    with VerticalScroll(classes="settings_pane"):
                        if not self._plugins_info:
                            yield Label("No plugins installed in plugins/ directory.", classes="settings_label")
                        else:
                            for p_name, p_info in self._plugins_info.items():
                                is_disabled = p_name in disabled_plugins
                                yield Horizontal(
                                    Label(f"🔌 Plugin: {p_name}", classes="settings_label"),
                                    Switch(value=not is_disabled, id=f"plugin_enable_{p_name}", classes="settings_widget"),
                                    classes="settings_row"
                                )
                                
                                # Render config fields
                                for k, v in p_info["config"].items():
                                    if k.lower() in ("enabled", "name", "version"):
                                        continue
                                    widget_id = f"plugin_cfg_{p_name}_{k}"
                                    if isinstance(v, bool):
                                        yield Horizontal(
                                            Label(f"  ↳ {k}:", classes="settings_label"),
                                            Switch(value=v, id=widget_id, classes="settings_widget"),
                                            classes="settings_row"
                                        )
                                    else:
                                        yield Horizontal(
                                            Label(f"  ↳ {k}:", classes="settings_label"),
                                            Input(value=str(v), id=widget_id, classes="settings_widget"),
                                            classes="settings_row"
                                        )
                                        
                                yield Label("─" * 70, classes="plugin_divider")

            with Horizontal(id="settings_actions"):
                yield Button("Cancel", id="btn_cancel", variant="error")
                yield Button("Save Settings", id="btn_save", variant="primary")

    def action_cancel(self) -> None:
        """Dismiss settings screen without saving."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "btn_cancel":
            self.action_cancel()
        elif event.button.id == "btn_save":
            self.action_save()

    def action_save(self) -> None:
        """Validate and save configuration values to settings.json."""
        # 1. Fetch values
        remote_llm = self.query_one("#remote_llm_url", Input).value.strip()
        remote_tts = self.query_one("#remote_tts_url", Input).value.strip()
        local_llm = self.query_one("#local_llm_url", Input).value.strip()

        # Validate remote SSL URLs (VULN-004 Enforcement)
        if remote_llm and not remote_llm.startswith("https://"):
            self.show_error("Remote LLM URL must use secure HTTPS protocol.")
            return
        if remote_tts and not remote_tts.startswith("https://"):
            self.show_error("Remote TTS URL must use secure HTTPS protocol.")
            return
            
        from engines.config import is_local_address
        if local_llm and not local_llm.startswith("https://"):
            if not is_local_address(local_llm):
                self.show_error("Local LLM API URL must use secure HTTPS protocol or a local loopback/private IP.")
                return

        # Parse and validate integers/floats
        try:
            auto_chat_load_limit = int(self.query_one("#auto_chat_load_limit", Input).value.strip())
            if auto_chat_load_limit <= 0:
                raise ValueError()
        except ValueError:
            self.show_error("Initial Chat Load Limit must be a positive integer.")
            return

        try:
            scroll_load_limit = int(self.query_one("#scroll_load_limit", Input).value.strip())
            if scroll_load_limit <= 0:
                raise ValueError()
        except ValueError:
            self.show_error("Scroll Load Limit must be a positive integer.")
            return

        try:
            streaming_delay = float(self.query_one("#streaming_delay", Input).value.strip())
            if streaming_delay < 0:
                raise ValueError()
        except ValueError:
            self.show_error("Streaming Delay must be a non-negative number.")
            return

        try:
            memory_limit = int(self.query_one("#memory_limit", Input).value.strip())
            if memory_limit <= 0:
                raise ValueError()
        except ValueError:
            self.show_error("Memory Message Limit must be a positive integer.")
            return

        try:
            repetition_penalty = float(self.query_one("#repetition_penalty", Input).value.strip())
            if repetition_penalty <= 0:
                raise ValueError()
        except ValueError:
            self.show_error("Repetition Penalty must be a positive number.")
            return

        try:
            max_tokens = int(self.query_one("#max_tokens", Input).value.strip())
            if max_tokens <= 0:
                raise ValueError()
        except ValueError:
            self.show_error("Max Response Tokens must be a positive integer.")
            return

        try:
            tts_rate = int(self.query_one("#tts_rate", Input).value.strip())
            if tts_rate <= 0:
                raise ValueError()
        except ValueError:
            self.show_error("TTS Speech Rate must be a positive integer.")
            return

        try:
            overhaul_candidate_count = int(self.query_one("#overhaul_candidate_count", Input).value.strip())
            if overhaul_candidate_count <= 0:
                raise ValueError()
        except ValueError:
            self.show_error("Overhaul Candidate Count must be a positive integer.")
            return

        try:
            inactivity_dashboard_timeout = int(self.query_one("#inactivity_dashboard_timeout", Input).value.strip())
            if inactivity_dashboard_timeout < 0:
                raise ValueError()
        except ValueError:
            self.show_error("Inactivity Dashboard Timeout must be a non-negative integer.")
            return

        try:
            privacy_screen_timeout = int(self.query_one("#privacy_screen_timeout", Input).value.strip())
            if privacy_screen_timeout < 0:
                raise ValueError()
        except ValueError:
            self.show_error("Inactivity Privacy Timeout must be a non-negative integer.")
            return

        try:
            max_input_tokens = int(self.query_one("#max_input_tokens", Input).value.strip())
            if max_input_tokens <= 0:
                raise ValueError()
        except ValueError:
            self.show_error("Max Context Tokens must be a positive integer.")
            return

        local_llm_keep_alive = self.query_one("#local_llm_keep_alive", Input).value.strip()

        # 2. Build updated settings dict
        updated_settings = {
            "interaction_mode": self.query_one("#interaction_mode", Select).value,
            "auto_recap_on_start": self.query_one("#auto_recap_on_start", Switch).value,
            "auto_chat_load": self.query_one("#auto_chat_load", Switch).value,
            "auto_chat_load_limit": auto_chat_load_limit,
            "scroll_load_limit": scroll_load_limit,
            "smooth_streaming": self.query_one("#smooth_streaming", Switch).value,
            "streaming_delay": streaming_delay,
            "image_protocol": self.query_one("#image_protocol", Select).value,
            "image_size": self.query_one("#image_size", Select).value,
            "suppress_errors": self.query_one("#suppress_errors", Switch).value,
            "inactivity_dashboard_timeout": inactivity_dashboard_timeout,
            "privacy_screen_timeout": privacy_screen_timeout,

            "default_llm_model": self.query_one("#default_llm_model", Input).value.strip(),
            "summarizer_model": self.query_one("#summarizer_model", Input).value.strip(),
            "local_utility_model": self.query_one("#local_utility_model", Input).value.strip(),
            "memory_limit": memory_limit,
            "repetition_penalty": repetition_penalty,
            "max_tokens": max_tokens,
            "max_input_tokens": max_input_tokens,
            "local_llm_keep_alive": local_llm_keep_alive,

            "tts_enabled": self.query_one("#tts_enabled", Switch).value,
            "character_speak": self.query_one("#character_speak", Switch).value,
            "speak_narration": self.query_one("#speak_narration", Switch).value,
            "default_tts_engine": self.query_one("#default_tts_engine", Select).value,
            "default_tts_voice": self.query_one("#default_tts_voice", Select).value,
            "narration_tts_voice": self.query_one("#narration_tts_voice", Select).value,
            "tts_rate": tts_rate,
            "show_tts_engine": self.query_one("#show_tts_engine", Switch).value,
            "unload_tts_after_generation": self.query_one("#unload_tts_after_generation", Switch).value,

            "remote_llm_url": remote_llm or None,
            "remote_tts_url": remote_tts or None,
            "local_llm_url": local_llm or None,
            "privacy_mode": self.query_one("#privacy_mode", Switch).value,
            "mcp_enabled": self.query_one("#mcp_enabled", Switch).value,

            "debug_mode": self.query_one("#debug_mode", Switch).value,
            "execute_command": self.query_one("#execute_command", Switch).value,
            "overhaul_pipeline_enabled": self.query_one("#overhaul_pipeline_enabled", Switch).value,
            "overhaul_instrumentation_enabled": self.query_one("#overhaul_instrumentation_enabled", Switch).value,
            "overhaul_state_enabled": self.query_one("#overhaul_state_enabled", Switch).value,
            "overhaul_memory_enabled": self.query_one("#overhaul_memory_enabled", Switch).value,
            "overhaul_planner_enabled": self.query_one("#overhaul_planner_enabled", Switch).value,
            "overhaul_candidates_enabled": self.query_one("#overhaul_candidates_enabled", Switch).value,
            "overhaul_critic_enabled": self.query_one("#overhaul_critic_enabled", Switch).value,
            "overhaul_candidate_count": overhaul_candidate_count,
            "overhaul_style_profile": self.query_one("#overhaul_style_profile", Select).value,
            "disabled_plugins": [],
        }
        
        # Save plugin settings
        for p_name, p_info in self._plugins_info.items():
            enable_switch = self.query_one(f"#plugin_enable_{p_name}", Switch)
            if not enable_switch.value:
                updated_settings["disabled_plugins"].append(p_name)
                
            if p_info["config"]:
                new_config = {}
                for k, v in p_info["config"].items():
                    if k.lower() in ("enabled", "name", "version"):
                        new_config[k] = v
                        continue
                    widget = self.query_one(f"#plugin_cfg_{p_name}_{k}")
                    if isinstance(v, bool):
                        new_config[k] = widget.value
                    elif isinstance(v, int):
                        try:
                            new_config[k] = int(widget.value.strip())
                        except ValueError:
                            new_config[k] = v
                    elif isinstance(v, float):
                        try:
                            new_config[k] = float(widget.value.strip())
                        except ValueError:
                            new_config[k] = v
                    else:
                        new_config[k] = widget.value.strip()
                
                import json
                try:
                    with open(p_info["config_path"], "w", encoding="utf-8") as f:
                        json.dump(new_config, f, indent=4)
                except Exception:
                    self.show_error(f"Failed to save config for plugin {p_name}.")
                    return

        # 3. Save atomically and dismiss screen returning settings dict
        from engines.config import update_settings
        if not update_settings(updated_settings):
            self.show_error("Failed to save settings. Please check directory permissions.")
            return

        self.dismiss(updated_settings)

    def show_error(self, message: str) -> None:
        """Display an error banner with validation failures."""
        err_label = self.query_one("#settings_error", Label)
        err_label.update(message)
        err_label.display = True

    def _get_plugin_info(self) -> dict:
        import os
        import json
        plugins = {}
        if not os.path.exists("plugins"):
            return plugins
            
        for item in os.listdir("plugins"):
            if item.startswith("_") or item.startswith("."):
                continue
                
            item_path = os.path.join("plugins", item)
            is_package = os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "__init__.py"))
            is_module = os.path.isfile(item_path) and item.endswith(".py")
            
            if not (is_package or is_module):
                continue
                
            plugin_name = item if is_package else item[:-3]
            config_path = os.path.join(item_path, "plugin.json") if is_package else f"{os.path.splitext(item_path)[0]}.json"
            
            config = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                except:
                    pass
                    
            plugins[plugin_name] = {
                "is_package": is_package,
                "config_path": config_path,
                "config": config
            }
        return plugins
