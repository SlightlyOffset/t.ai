import unittest
from unittest.mock import patch
from engines.responses import extract_scene_from_text, extract_scene_from_starter

class TestResponsesScene(unittest.TestCase):
    @patch("engines.responses.ollama.chat")
    @patch("engines.responses.get_setting", return_value="llama3.2")
    def test_extract_scene_from_text_success(self, mock_setting, mock_chat):
        # Set up mock response from ollama with High confidence
        mock_chat.return_value = {
            "message": {
                "content": "  'Dark Forest' | High  "
            }
        }
        
        scene = extract_scene_from_text("Let's go into the woods.", "*rustling leaves*")
        self.assertEqual(scene, "Dark Forest")
        
        # Verify ollama.chat arguments
        mock_chat.assert_called_once()
        args, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["model"], "llama3.2")
        self.assertEqual(kwargs["options"]["temperature"], 0.1)

    @patch("engines.responses.ollama.chat")
    @patch("engines.responses.get_setting", return_value="llama3.2")
    def test_extract_scene_from_text_low_confidence(self, mock_setting, mock_chat):
        # Set up mock response from ollama with Low confidence
        mock_chat.return_value = {
            "message": {
                "content": "Dark Forest | Low"
            }
        }
        scene = extract_scene_from_text("Let's go into the woods.", "*rustling leaves*")
        self.assertIsNone(scene)

    @patch("engines.responses.ollama.chat")
    @patch("engines.responses.get_setting", return_value="llama3.2")
    def test_extract_scene_from_text_unknown(self, mock_setting, mock_chat):
        mock_chat.return_value = {
            "message": {
                "content": "Unknown | Low"
            }
        }
        scene = extract_scene_from_text("Hello", "Hi there")
        self.assertIsNone(scene)

    @patch("engines.responses.ollama.chat")
    @patch("engines.responses.get_setting", return_value="llama3.2")
    def test_extract_scene_from_starter_success(self, mock_setting, mock_chat):
        mock_chat.return_value = {
            "message": {
                "content": "A Cozy Cafe | Medium"
            }
        }
        scene = extract_scene_from_starter("You find yourself sitting in a cozy coffee shop...")
        self.assertEqual(scene, "A Cozy Cafe")

if __name__ == "__main__":
    unittest.main()
