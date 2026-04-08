import unittest
from engines.utilities import is_chafa_available

class TestVisualAvatar(unittest.TestCase):
    def test_is_chafa_available(self):
        # We assume for the test environment that it might not be there, 
        # but the test should at least be able to call it.
        # Since I haven't implemented it yet, this should fail at import or call.
        self.assertIsInstance(is_chafa_available(), bool)

    def test_render_avatar_returns_string(self):
        # Even if the image doesn't exist, it should return a fallback string.
        from engines.utilities import render_avatar
        result = render_avatar("non_existent.png", width=35)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
        self.assertIn("No Image", result)

    def test_render_avatar_with_real_image(self):
        from engines.utilities import render_avatar, is_chafa_available
        if is_chafa_available():
            # Use the image the user mentioned
            path = "img/20251201_102409.jpg"
            result = render_avatar(path, width=35)
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)
            self.assertNotIn("No Image", result)
