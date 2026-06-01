import unittest
import sys
import os
from unittest.mock import MagicMock, patch, mock_open

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ui.menu import TaiMenu, format_rp

class TestMenu(unittest.TestCase):
    def test_format_rp(self):
        """Test the helper that italicizes narration."""
        text = "Hello *waves* how are you?"
        expected = "Hello [i][dim]waves[/dim][/i] how are you?"
        self.assertEqual(format_rp(text), expected)

    def test_format_rp_no_asterisks(self):
        self.assertEqual(format_rp("Hello"), "Hello")

    def test_format_rp_unclosed_asterisk(self):
        # Current implementation splits and italicizes odd indices
        # "Hello *waves" -> ["Hello ", "waves"] -> "Hello [i][dim]waves[/dim][/i]"
        # This is acceptable behavior for a simple regex-less helper.
        text = "Hello *waves"
        expected = "Hello [i][dim]waves[/dim][/i]"
        self.assertEqual(format_rp(text), expected)

    @patch('ui.menu.pick_profile')
    @patch('ui.menu.pick_user_profile')
    def test_app_init(self, mock_pick_user, mock_pick_char):
        """Ensure TaiMenu can be initialized with paths."""
        app = TaiMenu(char_path="profiles/test.json", user_path="user_profiles/test.json")
        self.assertEqual(app.char_path, "profiles/test.json")
        self.assertEqual(app.user_path, "user_profiles/test.json")

    @patch('ui.menu.TaiMenu.query')
    def test_get_last_user_message_from_ui(self, mock_query):
        """Test retrieving the last user message from UI bubbles."""
        mock_bubble = MagicMock()
        mock_bubble.raw_text = "Hello companion"
        mock_query.return_value.last.return_value = mock_bubble
        
        app = MagicMock(spec=TaiMenu)
        app.query = mock_query
        
        result = TaiMenu.get_last_user_message_from_ui(app)
        self.assertEqual(result, "Hello companion")
        mock_query.assert_called_once_with(".user_bubble")

    @patch('ui.menu.TaiMenu.get_last_user_message_from_ui')
    def test_resolve_regeneration_text_fallback(self, mock_get_last):
        """Test resolution of regeneration text falling back to UI when engine text differs or is missing."""
        app = MagicMock(spec=TaiMenu)
        app._resolve_regeneration_text = lambda et: TaiMenu._resolve_regeneration_text(app, et)
        app.get_last_user_message_from_ui = mock_get_last
        
        # Case 1: Engine text matches UI text
        mock_get_last.return_value = "Hello"
        self.assertEqual(app._resolve_regeneration_text("Hello"), "Hello")
        
        # Case 2: Engine text differs from UI text (mismatch / desync)
        mock_get_last.return_value = "Hello"
        self.assertEqual(app._resolve_regeneration_text("Previous"), "Hello")
        
        # Case 3: Engine text is None
        mock_get_last.return_value = "Hello"
        self.assertEqual(app._resolve_regeneration_text(None), "Hello")
        
        # Case 4: No UI text, fallback to engine text
        mock_get_last.return_value = None
        self.assertEqual(app._resolve_regeneration_text("Previous"), "Previous")

        # Case 5: Engine text is empty string (continuation), should return empty string directly
        mock_get_last.return_value = "Hello"
        self.assertEqual(app._resolve_regeneration_text(""), "")

    @patch('ui.menu.update_setting')
    def test_on_select_changed_interaction_mode(self, mock_update_setting):
        """Test on_select_changed updates interaction_mode when interaction_mode_select changes."""
        app = MagicMock(spec=TaiMenu)
        app.on_select_changed = lambda event: TaiMenu.on_select_changed(app, event)
        app.add_message = MagicMock()

        # Select RP Mode
        event_rp = MagicMock()
        event_rp.select.id = "interaction_mode_select"
        event_rp.value = "rp"
        app.on_select_changed(event_rp)
        mock_update_setting.assert_any_call("interaction_mode", "rp")
        app.add_message.assert_any_call("Interaction mode set to [bold]RP[/bold]", role="system")

        # Select Casual Mode
        event_casual = MagicMock()
        event_casual.select.id = "interaction_mode_select"
        event_casual.value = "casual"
        app.on_select_changed(event_casual)
        mock_update_setting.assert_any_call("interaction_mode", "casual")
        app.add_message.assert_any_call("Interaction mode set to [bold]CASUAL[/bold]", role="system")

    @patch('ui.menu.get_setting')
    def test_on_select_changed_interaction_mode_null_fallback(self, mock_get_setting):
        """Test on_select_changed reverts interaction_mode_select when null is selected."""
        app = MagicMock(spec=TaiMenu)
        app.on_select_changed = lambda event: TaiMenu.on_select_changed(app, event)
        
        mock_get_setting.return_value = "casual"
        
        event_null = MagicMock()
        event_null.select.id = "interaction_mode_select"
        from textual.widgets import Select
        event_null.value = Select.NULL
        
        app.on_select_changed(event_null)
        # Verify it reverted back to the previous mode
        self.assertEqual(event_null.select.value, "casual")

    @patch('ui.menu.TaiMenu.set_timer')
    @patch('ui.menu.TaiMenu.query_one')
    def test_add_message_system_tip_timers(self, mock_query_one, mock_set_timer):
        """Test that system, tip, and command messages mount and trigger set_timer with proper intervals."""
        class DummyMenu(TaiMenu):
            def __init__(self):
                pass
        app = DummyMenu()
        app.query_one = mock_query_one
        app.set_timer = mock_set_timer
        
        mock_container = MagicMock()
        mock_query_one.return_value = mock_container
        
        # Test system message -> 5.0s
        app.add_message("System Message", role="system")
        self.assertTrue(mock_container.mount.called)
        mock_set_timer.assert_called_with(5.0, unittest.mock.ANY)
        
        # Reset mocks
        mock_container.mount.reset_mock()
        mock_set_timer.reset_mock()
        
        # Test tip message -> 10.0s
        app.add_message("Tip Message", role="tip_message")
        self.assertTrue(mock_container.mount.called)
        mock_set_timer.assert_called_with(10.0, unittest.mock.ANY)

        # Reset mocks
        mock_container.mount.reset_mock()
        mock_set_timer.reset_mock()

        # Test command message -> 10.0s
        app.add_message("Command Output", role="command")
        self.assertTrue(mock_container.mount.called)
        mock_set_timer.assert_called_with(10.0, unittest.mock.ANY)

        # Reset mocks
        mock_container.mount.reset_mock()
        mock_set_timer.reset_mock()

        # Test help command output -> no timer scheduled
        app.add_message("[AVAILABLE COMMANDS]\n  //help", role="command")
        self.assertTrue(mock_container.mount.called)
        self.assertFalse(mock_set_timer.called)

        # Reset mocks
        mock_container.mount.reset_mock()
        mock_set_timer.reset_mock()

        # Test error command output -> no timer scheduled
        app.add_message("[ERROR] Something failed", role="command")
        self.assertTrue(mock_container.mount.called)
        self.assertFalse(mock_set_timer.called)

    @patch('ui.menu.handle_command_input')
    @patch('ui.menu.memory_manager')
    @patch('ui.menu.get_user_message_number')
    @patch('ui.menu.TaiMenu.stream_response')
    def test_on_chat_input_submitted_command_handling(self, mock_stream, mock_get_msg_num, mock_mem, mock_handle_command):
        """Test that chat input submitted with '//' is handled as a command and doesn't add user bubbles."""
        import asyncio
        class DummyMenu(TaiMenu):
            def __init__(self):
                self.history_profile_name = "test_profile"
                self.char_path = "profiles/test.json"
                self.user_path = "user_profiles/test.json"
            def format_rp(self, text, role="user"):
                return text

        app = DummyMenu()
        app.add_message = MagicMock()
        app.update_sidebar = MagicMock()
        app.reload_chat_from_history = MagicMock()
        app.check_for_rolling_summary = MagicMock()
        app.action_open_settings = MagicMock()
        app.run_manual_compression = MagicMock()

        # Mock Event
        class MockEvent:
            def __init__(self, value):
                self.value = value

        # 1. Command with command_noop return
        mock_handle_command.return_value = {"type": "command_noop"}
        asyncio.run(app.on_chat_input_submitted(MockEvent("//invalid")))
        
        # Verify that add_message was called with role="command", NOT role="user"
        app.add_message.assert_any_call("[SYSTEM] Recognized command pattern but no action taken: Non-existent command.", role="command")
        # Check that role="user" was never added
        for call in app.add_message.call_args_list:
            self.assertNotEqual(call[1].get("role"), "user")

        app.add_message.reset_mock()

        # 2. Command with command_success return
        mock_handle_command.return_value = {"type": "command_success", "messages": ["Line 1", "Line 2"]}
        asyncio.run(app.on_chat_input_submitted(MockEvent("//toggle clear")))
        app.add_message.assert_any_call("Line 1\nLine 2", role="command")
        for call in app.add_message.call_args_list:
            self.assertNotEqual(call[1].get("role"), "user")

        app.add_message.reset_mock()

        # 2b. Test command slash normalization with single slash '/'
        asyncio.run(app.on_chat_input_submitted(MockEvent("/toggle clear")))
        mock_handle_command.assert_called_with("//toggle clear", "test_profile")
        app.add_message.reset_mock()

        # 2c. Test command slash normalization with multiple slashes '///'
        asyncio.run(app.on_chat_input_submitted(MockEvent("///toggle clear")))
        mock_handle_command.assert_called_with("//toggle clear", "test_profile")
        app.add_message.reset_mock()

        # 3. Regular chat message
        mock_get_msg_num.return_value = 1
        asyncio.run(app.on_chat_input_submitted(MockEvent("Hello world")))
        app.add_message.assert_called_once_with("Hello world", role="user", message_number=1, raw_text="Hello world")
        mock_stream.assert_called_once_with("Hello world", message_number=2)

    @patch('ui.menu.handle_command_input')
    @patch('ui.menu.memory_manager')
    @patch('ui.menu.get_user_message_number')
    @patch('ui.menu.TaiMenu.stream_response')
    @patch('ui.menu.TaiMenu.query_one')
    def test_on_chat_input_submitted_reset_command(self, mock_query_one, mock_stream, mock_get_msg_num, mock_mem, mock_handle_command):
        """Test that chat input submitted with '//reset' clears the UI and calls print_starter_message."""
        import asyncio
        class DummyMenu(TaiMenu):
            def __init__(self):
                self.history_profile_name = "test_profile"
                self.char_path = "profiles/test.json"
                self.user_path = "user_profiles/test.json"
                self.character_profile = {}
                self.user_profile = {}
                self.ch_name = "TestChar"
                self.user_name = "TestUser"
                self.char_name_lbl_color = "red"
                self.user_name_lbl_color = "blue"

        app = DummyMenu()
        app.add_message = MagicMock()
        app.update_sidebar = MagicMock()
        app.print_starter_message = MagicMock()
        
        mock_container = MagicMock()
        mock_child = MagicMock()
        mock_container.children = [mock_child]
        mock_query_one.return_value = mock_container

        # Mock Event
        class MockEvent:
            def __init__(self, value):
                self.value = value

        mock_handle_command.return_value = {"type": "command_success", "messages": ["Wiped history"]}
        
        # Test active profile reset
        asyncio.run(app.on_chat_input_submitted(MockEvent("//reset")))
        
        # Verify it cleared chat container children, and reprinted starter message
        self.assertTrue(mock_child.remove.called)
        self.assertTrue(app.print_starter_message.called)
        self.assertTrue(app.update_sidebar.called)

    @patch('ui.menu.iterate_response_events')
    @patch('ui.menu.memory_manager')
    @patch('ui.menu.get_setting')
    @patch('builtins.open', new_callable=mock_open, read_data='{"name": "Nova", "llm_model": "test"}')
    def test_response_worker_pagination_logic(self, mock_file, mock_get_setting, mock_memory_manager, mock_iterate):
        """Test that pagination indicator is only added if is_regeneration is True."""
        class DummyMenu(TaiMenu):
            def __init__(self):
                self.history_profile_name = "test_profile"
                self.user_profile = {"name": "TestUser"}
                self.character_profile = {"name": "Nova", "llm_model": "test-model"}
            
            @property
            def app(self):
                mock_app = MagicMock()
                mock_app.call_from_thread = lambda func, *args, **kwargs: func(*args, **kwargs)
                return mock_app

            def format_rp(self, text, role="user"):
                return text

        app = DummyMenu()
        app.update_sidebar = MagicMock()
        app.check_for_rolling_summary = MagicMock()

        # Mock event stream: chunk, then complete
        mock_iterate.return_value = [
            {"type": "chunk", "full_response": "Hello!"},
            {"type": "complete", "full_response": "Hello!"}
        ]

        # Mock history with alternatives
        mock_history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "Hello!", "alternatives": ["Old content", "Hello!"], "selected_index": 1}
        ]
        mock_memory_manager.load_history.return_value = mock_history

        # Mock widgets
        container = MagicMock()
        ai_msg = MagicMock()
        header = " Nova:"

        # Case 1: is_regeneration = False (should NOT update with pagination indicator)
        TaiMenu.response_worker.__wrapped__(
            app,
            message="hi",
            is_regeneration=False,
            container=container,
            ai_msg=ai_msg,
            header=header
        )
        # Verify that ai_msg.update was called with the chunk but NEVER with "< 2/2 >" indicator
        for call in ai_msg.update.call_args_list:
            self.assertNotIn("<", call[0][0])
            self.assertNotIn(">", call[0][0])

        # Reset mock
        ai_msg.reset_mock()

        # Case 2: is_regeneration = True (should update with pagination indicator)
        TaiMenu.response_worker.__wrapped__(
            app,
            message="hi",
            is_regeneration=True,
            container=container,
            ai_msg=ai_msg,
            header=header
        )
        # Verify that ai_msg.update was called with the pagination indicator at the end
        # Since the mock database already has the new alternative in the mock history, it should show "< 2/2 >"
        ai_msg.update.assert_called_with(" Nova:\nHello!\n\n[dim]< 2/2 >[/dim]")

    @patch('ui.menu.memory_manager')
    @patch('ui.menu.TaiMenu.stream_response')
    def test_empty_chat_input_submitted_triggers_continuation(self, mock_stream, mock_memory_manager):
        """Verify that submitting an empty chat input triggers bot continuation."""
        import asyncio
        class DummyMenu(TaiMenu):
            def __init__(self):
                self.history_profile_name = "test_profile"
                self.char_path = "profiles/test.json"
                self.user_path = "user_profiles/test.json"
            def format_rp(self, text, role="user"):
                return text

        app = DummyMenu()
        app.add_message = MagicMock()

        # Mock Event with empty value
        class MockEvent:
            def __init__(self, value):
                self.value = value

        mock_memory_manager.get_history_length.return_value = 5
        mock_memory_manager.load_history.return_value = [{"role": "user", "content": "msg"}] * 6

        # Call on_chat_input_submitted with empty message
        asyncio.run(app.on_chat_input_submitted(MockEvent("   ")))

        # Check that user bubble was NEVER added
        app.add_message.assert_not_called()

        # Check that memory_manager set pending user message to empty string
        mock_memory_manager.set_pending_user_message.assert_called_once_with("test_profile", "")

        # Check that stream_response was called with empty message and Turn 7
        mock_stream.assert_called_once_with("", message_number=7)

    def test_add_message_hides_empty_user_messages(self):
        class DummyMenu(TaiMenu):
            def __init__(self):
                pass
        app = DummyMenu()
        app.query_one = MagicMock()
        
        # Call add_message with empty text for user
        app.add_message("", role="user")
        # If it returns early, query_one should NOT be called (no widget mounted)
        app.query_one.assert_not_called()

    def test_chat_input_on_key_posts_empty_submitted_event(self):
        """Verify that pressing Enter when ChatInput is empty posts a Submitted event with an empty string."""
        from textual.events import Key
        from ui.menu import ChatInput
        
        input_widget = ChatInput()
        input_widget.text = "   "  # whitespace only
        input_widget.post_message = MagicMock()
        
        # Simulate pressing "enter"
        mock_event = MagicMock(spec=Key)
        mock_event.key = "enter"
        
        input_widget.on_key(mock_event)
        
        # Verify that prevent_default was called on the event
        mock_event.prevent_default.assert_called_once()
        
        # Verify that post_message was called with a Submitted message with empty value
        # It may also post other messages like TextArea.Changed when setting self.text = ""
        submitted_msg = None
        for call_args in input_widget.post_message.call_args_list:
            msg = call_args[0][0]
            if isinstance(msg, ChatInput.Submitted):
                submitted_msg = msg
                break
        self.assertIsNotNone(submitted_msg, "ChatInput.Submitted was not posted")
        self.assertEqual(submitted_msg.value, "")
        
        # Verify that text is cleared and height is reset to 3
        self.assertEqual(input_widget.text, "")
        self.assertEqual(input_widget.height, 3)

    @patch("engines.responses.active_post_process_threads")
    def test_on_unmount_joins_alive_threads(self, mock_threads):
        class DummyMenu(TaiMenu):
            def __init__(self):
                pass
        app = DummyMenu()
        
        # Mock active thread
        mock_thread_alive = MagicMock()
        mock_thread_alive.is_alive.return_value = True
        mock_thread_dead = MagicMock()
        mock_thread_dead.is_alive.return_value = False
        
        # Populate mock active_post_process_threads
        mock_threads.__iter__.return_value = [mock_thread_alive, mock_thread_dead]
        
        app.on_unmount()
        
        # Verify that only the alive thread was joined
        mock_thread_alive.join.assert_called_once_with()
        mock_thread_dead.join.assert_not_called()

    @patch("engines.responses.active_post_process_threads")
    def test_action_quit_with_no_alive_threads(self, mock_threads):
        class DummyMenu(TaiMenu):
            def __init__(self):
                self.exit_called = False
            def exit(self):
                self.exit_called = True
        app = DummyMenu()
        mock_threads.__iter__.return_value = []
        
        import asyncio
        asyncio.run(app.action_quit())
        self.assertTrue(app.exit_called)

    @patch("engines.responses.active_post_process_threads")
    def test_action_quit_with_alive_threads(self, mock_threads):
        class DummyMenu(TaiMenu):
            def __init__(self):
                self.pushed_screen = None
                self.run_worker_called_with = None
            def push_screen(self, screen):
                self.pushed_screen = screen
            def run_worker(self, coro):
                self.run_worker_called_with = coro
        app = DummyMenu()
        mock_thread_alive = MagicMock()
        mock_thread_alive.is_alive.return_value = True
        mock_threads.__iter__.return_value = [mock_thread_alive]
        
        import asyncio
        asyncio.run(app.action_quit())
        
        from ui.menu import ExitSavingScreen
        self.assertIsInstance(app.pushed_screen, ExitSavingScreen)
        self.assertIsNotNone(app.run_worker_called_with)
        app.run_worker_called_with.close()

    def test_wait_and_exit(self):
        class DummyMenu(TaiMenu):
            def __init__(self):
                self.exit_called = False
            def exit(self):
                self.exit_called = True
        app = DummyMenu()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        
        import asyncio
        asyncio.run(app._wait_and_exit([mock_thread]))
        
        mock_thread.join.assert_called_once_with()
        self.assertTrue(app.exit_called)

if __name__ == "__main__":
    unittest.main()
