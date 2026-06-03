import unittest
from unittest.mock import patch, MagicMock
import os
from engines.tts_module import clean_text_for_tts, generate_audio

class TestTTSModule(unittest.TestCase):

    def test_clean_text_for_tts_keep_narration(self):
        text = "*He smiles* Hello there!"
        cleaned = clean_text_for_tts(text, speak_narration=True)
        self.assertEqual(cleaned, "He smiles Hello there!")

    def test_clean_text_for_tts_strip_narration(self):
        text = "*He smiles* Hello there!"
        cleaned = clean_text_for_tts(text, speak_narration=False)
        self.assertEqual(cleaned, "Hello there!")

    @patch('engines.tts_module.get_setting')
    @patch('engines.tts_module.is_online')
    @patch('engines.tts_module.EDGE_AVAILABLE', True)
    @patch('engines.tts_module.generate_edge_tts', new_callable=MagicMock)
    @patch('asyncio.run')
    def test_generate_audio_uses_edge_tts_by_default(self, mock_async_run, mock_generate_edge, mock_is_online, mock_get_setting):
        mock_is_online.return_value = True
        mock_get_setting.side_effect = lambda key, default=None: {
            "default_tts_voice": "en-GB-SoniaNeural",
            "tts_engine": "edge-tts"
        }.get(key, default)
        
        result = generate_audio("Hello", "test.mp3")
        self.assertTrue(result)
        # Verify it attempted to run the async generate_edge_tts
        self.assertTrue(mock_async_run.called)

    @patch('engines.tts_module.get_setting')
    def test_generate_audio_returns_false_when_tts_disabled(self, mock_get_setting):
        mock_get_setting.side_effect = lambda key, default=None: False if key == "tts_enabled" else default
        result = generate_audio("Hello", "test.mp3")
        self.assertFalse(result)

    def test_voices_directory_exists(self):
        self.assertTrue(os.path.exists("voices"))

    def test_cache_directory_exists(self):
        from engines.audio_cache import CACHE_DIR
        self.assertTrue(os.path.exists(CACHE_DIR))

if __name__ == '__main__':
    unittest.main()
