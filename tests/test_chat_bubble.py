import unittest
from unittest.mock import MagicMock, patch
from ui.menu import ChatBubble, ImageBubble
from textual.app import App


class TestChatBubble(unittest.TestCase):
    def setUp(self):
        self.orig_app = ChatBubble.app

    def tearDown(self):
        ChatBubble.app = self.orig_app

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
        # Header, Text 1, Fallback image, Text 2
        self.assertEqual(len(widgets), 4)
        
        # Verify child content
        self.assertEqual(str(widgets[0].render()), " Nova:")
        self.assertEqual(str(widgets[1].render()), "Check this: ")
        self.assertEqual(str(widgets[2].render()), "🖼️ [Image: pic]")
        self.assertEqual(str(widgets[3].render()), " and another.")

    @patch('ui.menu.get_setting')
    def test_chat_bubble_with_image_indicator(self, mock_get_setting):
        """When image protocol is NOT 'none', ChatBubble shows an inline dim indicator."""
        mock_get_setting.return_value = "auto"
        
        mock_app = MagicMock()
        mock_app.format_rp = lambda text, role: text
        
        bubble = ChatBubble(
            header=" Nova:",
            raw_content="Here: ![pic](cache/image.png)",
            role="assistant"
        )
        type(bubble).app = property(lambda self: mock_app)
        
        widgets = list(bubble.compose())
        
        # Header, Text, Inline indicator (NOT a loading placeholder)
        self.assertEqual(len(widgets), 3)
        self.assertEqual(str(widgets[0].render()), " Nova:")
        self.assertEqual(str(widgets[1].render()), "Here: ")
        # The indicator is a dim text label, not an optimizing placeholder
        self.assertIn("bubble_image_indicator", widgets[2].classes)

    @patch('ui.menu.get_setting')
    def test_chat_bubble_no_inline_loading_placeholders(self, mock_get_setting):
        """ChatBubble should no longer yield loading placeholders for images."""
        mock_get_setting.return_value = "auto"

        mock_app = MagicMock()
        mock_app.format_rp = lambda text, role: text

        bubble = ChatBubble(
            header=" Nova:",
            raw_content="Look: ![a](img/a.png) ![b](img/b.png)",
            role="assistant"
        )
        type(bubble).app = property(lambda self: mock_app)

        widgets = list(bubble.compose())
        
        # Ensure NO widgets have the old loading class
        for widget in widgets:
            self.assertNotIn("bubble_image_loading", getattr(widget, "classes", set()))
            self.assertFalse(hasattr(widget, "image_url"))

    @patch('ui.menu.get_setting')
    def test_chat_bubble_pagination_placement_last_text_chunk(self, mock_get_setting):
        """Pagination indicator should be appended to the LAST text chunk if there are multiple text chunks (e.g. split by images)."""
        mock_get_setting.return_value = "auto"
        
        mock_app = MagicMock()
        mock_app.format_rp = lambda text, role: text
        
        msg_data = {"alternatives": ["A", "B"], "selected_index": 0}
        
        bubble = ChatBubble(
            header=" Nova:",
            raw_content="First text chunk. ![pic](cache/image.png) Second text chunk.",
            role="assistant",
            msg_data=msg_data
        )
        type(bubble).app = property(lambda self: mock_app)
        
        widgets = list(bubble.compose())
        
        # widgets[0]: Header
        # widgets[1]: First text chunk (should NOT contain the indicator)
        # widgets[2]: Image indicator
        # widgets[3]: Second text chunk (should contain the indicator "< 1/2 >")
        
        self.assertEqual(len(widgets), 4)
        self.assertEqual(str(widgets[1].render()), "First text chunk. ")
        self.assertIn("< 1/2 >", str(widgets[3].render()))
        self.assertIn("Second text chunk.", str(widgets[3].render()))


class TestImageBubble(unittest.TestCase):
    def test_image_bubble_compose(self):
        """ImageBubble yields a toggle header and an image container."""
        bubble = ImageBubble(
            image_url="cache/optimized/test.png",
            alt="Test Image",
            role="assistant",
        )
        widgets = list(bubble.compose())
        
        # Should yield: toggle header Static, image container Vertical
        self.assertEqual(len(widgets), 2)
        # Toggle header
        self.assertIn("image_toggle_header", widgets[0].classes)
        self.assertIn("Show Image", str(widgets[0].render()))
        self.assertIn("Test Image", str(widgets[0].render()))
        # Image container
        self.assertIn("image_container", widgets[1].classes)

    def test_image_bubble_classes(self):
        """ImageBubble should have message and image_bubble_wrap classes."""
        bubble = ImageBubble(
            image_url="test.png",
            alt="",
            role="user",
        )
        self.assertIn("message", bubble.classes)
        self.assertIn("image_bubble_wrap", bubble.classes)

    def test_image_bubble_stores_metadata(self):
        """ImageBubble stores image URL, alt text, and role."""
        bubble = ImageBubble(
            image_url="https://example.com/photo.jpg",
            alt="A photo",
            role="user",
        )
        self.assertEqual(bubble.image_url, "https://example.com/photo.jpg")
        self.assertEqual(bubble.alt, "A photo")
        self.assertEqual(bubble.role, "user")

    def test_image_bubble_default_collapsed(self):
        """ImageBubble starts collapsed by default."""
        bubble = ImageBubble(image_url="test.png")
        self.assertTrue(bubble.collapsed)


if __name__ == "__main__":
    unittest.main()
