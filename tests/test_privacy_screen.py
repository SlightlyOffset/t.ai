import unittest
import time
from unittest.mock import patch, MagicMock, PropertyMock, AsyncMock
from textual import events

class TestPrivacyScreen(unittest.TestCase):
    """Unit tests for the inactivity PrivacyScreen lock mechanism."""

    @patch('ui.menu.TaiMenu.start_tts_worker')
    @patch('ui.menu.TaiMenu.push_screen')
    @patch('ui.menu.get_setting')
    def test_check_inactivity_lock_triggers(self, mock_get_setting, mock_push, mock_tts):
        """Test that PrivacyScreen is pushed when inactivity timeout is exceeded."""
        from ui.menu import TaiMenu
        from ui.PrivacyScreen import PrivacyScreen
        
        # Configure settings: privacy timeout is 3 minutes
        mock_get_setting.return_value = 3
        
        app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
        app._last_user_activity = time.time() - 200  # 200 seconds ago (> 180 seconds/3 min)
        
        # Mock active screen (not dashboard or privacy screen)
        with patch('ui.menu.TaiMenu.screen', new_callable=PropertyMock) as mock_screen:
            mock_screen.return_value = MagicMock()
            app.check_inactivity_lock()
            
        self.assertTrue(mock_push.called)
        called_screen = mock_push.call_args[0][0]
        self.assertIsInstance(called_screen, PrivacyScreen)

    @patch('ui.menu.TaiMenu.start_tts_worker')
    @patch('ui.menu.TaiMenu.push_screen')
    @patch('ui.menu.get_setting')
    def test_check_inactivity_lock_does_not_trigger_if_active(self, mock_get_setting, mock_push, mock_tts):
        """Test that PrivacyScreen is not pushed if inactivity timeout is not yet met."""
        from ui.menu import TaiMenu
        
        # Configure settings: privacy timeout is 3 minutes
        mock_get_setting.return_value = 3
        
        app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
        app._last_user_activity = time.time() - 100  # 100 seconds ago (< 180 seconds/3 min)
        
        with patch('ui.menu.TaiMenu.screen', new_callable=PropertyMock) as mock_screen:
            mock_screen.return_value = MagicMock()
            app.check_inactivity_lock()
            
        self.assertFalse(mock_push.called)

    @patch('ui.menu.TaiMenu.start_tts_worker')
    @patch('ui.menu.TaiMenu.push_screen')
    @patch('ui.menu.get_setting')
    def test_check_inactivity_lock_disabled(self, mock_get_setting, mock_push, mock_tts):
        """Test that PrivacyScreen is not pushed if privacy timeout is 0."""
        from ui.menu import TaiMenu
        
        # Configure settings: privacy timeout is 0 (disabled)
        mock_get_setting.return_value = 0
        
        app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
        app._last_user_activity = time.time() - 1000
        
        app.check_inactivity_lock()
        self.assertFalse(mock_push.called)

    @patch('ui.menu.TaiMenu.start_tts_worker')
    @patch('ui.menu.TaiMenu.push_screen')
    @patch('ui.menu.get_setting')
    def test_check_inactivity_lock_skipped_on_dashboard(self, mock_get_setting, mock_push, mock_tts):
        """Test that PrivacyScreen is skipped if active screen is already DashboardScreen or PrivacyScreen."""
        from ui.menu import TaiMenu
        from ui.DashboardScreen import DashboardScreen
        from ui.PrivacyScreen import PrivacyScreen
        
        mock_get_setting.return_value = 3
        app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
        app._last_user_activity = time.time() - 1000
        
        # Mock active screen as DashboardScreen
        with patch('ui.menu.TaiMenu.screen', new_callable=PropertyMock) as mock_screen:
            mock_screen.return_value = DashboardScreen()
            app.check_inactivity_lock()
        self.assertFalse(mock_push.called)
        
        # Mock active screen as PrivacyScreen
        with patch('ui.menu.TaiMenu.screen', new_callable=PropertyMock) as mock_screen:
            mock_screen.return_value = PrivacyScreen()
            app.check_inactivity_lock()
        self.assertFalse(mock_push.called)

    @patch('textual.app.App.on_event', new_callable=AsyncMock)
    @patch('ui.menu.TaiMenu.start_tts_worker')
    def test_on_event_resets_activity(self, mock_tts, mock_super_on_event):
        """Test that on_event resets the inactivity timer on keys or mouse events."""
        from ui.menu import TaiMenu
        import asyncio
        
        app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
        app._last_user_activity = 0.0
        
        # Trigger Key event
        key_event = events.Key("enter", character="enter")
        asyncio.run(app.on_event(key_event))
        self.assertNotEqual(app._last_user_activity, 0.0)
        
        # Reset and trigger Mouse event
        app._last_user_activity = 0.0
        mouse_event = events.MouseMove(widget=app, x=10, y=10, delta_x=1, delta_y=1, button=0, shift=False, ctrl=False, meta=False)
        asyncio.run(app.on_event(mouse_event))
        self.assertNotEqual(app._last_user_activity, 0.0)

    def test_privacy_screen_dismissal(self):
        """Test that PrivacyScreen can be composed and dismissed with action_unlock."""
        from ui.PrivacyScreen import PrivacyScreen
        screen = PrivacyScreen()
        
        dismiss_result = None
        def mock_dismiss(result):
            nonlocal dismiss_result
            dismiss_result = result
        screen.dismiss = mock_dismiss
        
        screen.action_unlock()
        self.assertTrue(dismiss_result)

    @patch('ui.menu.TaiMenu.start_tts_worker')
    @patch('ui.menu.TaiMenu.push_screen')
    @patch('ui.menu.get_setting')
    def test_check_inactivity_lock_no_double_push(self, mock_get_setting, mock_push, mock_tts):
        """Test that a second PrivacyScreen is not pushed when _privacy_screen_active flag is set."""
        from ui.menu import TaiMenu

        mock_get_setting.return_value = 3
        app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
        app._last_user_activity = time.time() - 1000
        app._privacy_screen_active = True  # Flag already set (screen is active)

        with patch('ui.menu.TaiMenu.screen', new_callable=PropertyMock) as mock_screen:
            mock_screen.return_value = MagicMock()
            app.check_inactivity_lock()

        self.assertFalse(mock_push.called, "Should not push a second PrivacyScreen when flag is set")

    @patch('ui.menu.TaiMenu.start_tts_worker')
    @patch('ui.menu.TaiMenu.push_screen')
    def test_action_open_dashboard_blocked_on_privacy_screen(self, mock_push, mock_tts):
        """Test that ctrl+g does not open Dashboard while PrivacyScreen is active."""
        from ui.menu import TaiMenu
        from ui.PrivacyScreen import PrivacyScreen

        app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")

        with patch('ui.menu.TaiMenu.screen', new_callable=PropertyMock) as mock_screen:
            mock_screen.return_value = PrivacyScreen()
            app.action_open_dashboard()

        self.assertFalse(mock_push.called, "Dashboard should not open while PrivacyScreen is showing")

    def test_on_privacy_screen_dismissed_clears_flag(self):
        """Test that dismissing the privacy screen clears the _privacy_screen_active flag."""
        from ui.menu import TaiMenu

        app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
        app._privacy_screen_active = True
        app.on_privacy_screen_dismissed(True)

        self.assertFalse(app._privacy_screen_active, "_privacy_screen_active should be False after dismissal")
        self.assertNotEqual(app._last_user_activity, 0.0, "Activity timer should be reset on dismissal")

if __name__ == '__main__':
    unittest.main()
