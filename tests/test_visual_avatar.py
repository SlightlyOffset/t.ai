import unittest
from engines.utilities import is_chafa_available

class TestVisualAvatar(unittest.TestCase):
    def test_is_chafa_available(self):
        # We assume for the test environment that it might not be there, 
        # but the test should at least be able to call it.
        # Since I haven't implemented it yet, this should fail at import or call.
        self.assertIsInstance(is_chafa_available(), bool)
