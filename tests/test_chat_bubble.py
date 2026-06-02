import unittest
from unittest.mock import MagicMock, patch
from ui.menu import ChatBubble
from textual.app import App


class TestChatBubble(unittest.TestCase):
    @patch('ui.menu.get_setting')
    def test_chat_bubble_text_only(self, mock_get_setting):
        # Mock image protocol to "none"
        mock_get_setting.return_value = "none"
        
        # Mock app instance
        mock_app = MagicMock()
        mock_app.format_rp = lambda text, role: text
        
        bubble = ChatBubble(
            header=" Nova:",
            raw_content="Check this: ![pic](cache/image.png) and another.",
            role="assistant"
        )
        # Override the read-only app property
        type(bubble).app = property(lambda self: mock_app)
        
        # Get composed widgets from generator
        widgets = list(bubble.compose())
        
        # Verify the children widgets were composed correctly
        self.assertEqual(len(widgets), 4) # Header, Text 1, Fallback image, Text 2
        
        # Verify child content
        self.assertEqual(str(widgets[0].render()), " Nova:")
        self.assertEqual(str(widgets[1].render()), "Check this: ")
        self.assertEqual(str(widgets[2].render()), "🖼️ [Image: pic]")
        self.assertEqual(str(widgets[3].render()), " and another.")

    @patch('ui.menu.get_setting')
    def test_chat_bubble_with_loading_placeholder(self, mock_get_setting):
        # Mock image protocol to "auto"
        mock_get_setting.return_value = "auto"
        
        # Mock app instance
        mock_app = MagicMock()
        mock_app.format_rp = lambda text, role: text
        
        bubble = ChatBubble(
            header=" Nova:",
            raw_content="Here: ![pic](cache/image.png)",
            role="assistant"
        )
        # Override the read-only app property
        type(bubble).app = property(lambda self: mock_app)
        
        widgets = list(bubble.compose())
        
        self.assertEqual(len(widgets), 3) # Header, Text, Placeholder
        self.assertEqual(str(widgets[0].render()), " Nova:")
        self.assertEqual(str(widgets[1].render()), "Here: ")
        self.assertEqual(str(widgets[2].render()), "⏳ [Optimizing Image... pic]")
        self.assertEqual(widgets[2].image_url, "cache/image.png")


if __name__ == "__main__":
    unittest.main()
