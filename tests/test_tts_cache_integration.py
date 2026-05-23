import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the project root to sys.path to import engines
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engines.tts_module import generate_audio

class TestTTSCacheIntegration(unittest.TestCase):

    @patch('engines.tts_module.get_setting')
    @patch('engines.tts_module.get_cache_path')
    @patch('engines.tts_module.os.path.exists')
    @patch('engines.tts_module.shutil.copy')
    @patch('engines.tts_module.is_online')
    @patch('engines.tts_module.EDGE_AVAILABLE', True)
    def test_cache_hit_skips_generation(self, mock_is_online, mock_copy, mock_exists, mock_get_cache_path, mock_get_setting):
        mock_get_setting.return_value = True # tts_enabled
        mock_is_online.return_value = True
        mock_exists.return_value = True # Cache hit!
        mock_get_cache_path.return_value = "cache/hashed_file.wav"
        
        # We patch generate_edge_tts to ensure it is NOT called
        with patch('engines.tts_module.generate_edge_tts') as mock_gen:
            result = generate_audio("Hello", "output.mp3")
            
            self.assertTrue(result)
            mock_copy.assert_called_with("cache/hashed_file.wav", "output.mp3")
            mock_gen.assert_not_called()

    @patch('engines.tts_module.get_setting')
    @patch('engines.tts_module.save_to_cache')
    @patch('engines.tts_module.get_cache_path')
    @patch('engines.tts_module.os.path.exists')
    @patch('engines.tts_module.asyncio.run')
    @patch('engines.tts_module.is_online')
    @patch('engines.tts_module.EDGE_AVAILABLE', True)
    def test_cache_miss_triggers_generation_and_save(self, mock_is_online, mock_async_run, mock_exists, mock_get_cache_path, mock_save_to_cache, mock_get_setting):
        mock_get_setting.return_value = True # tts_enabled
        mock_is_online.return_value = True
        
        def mock_exists_side_effect(path):
            if "settings.json" in str(path): return True
            if "hashed_file.wav" in str(path): return False
            if "output.mp3" in str(path): return True
            return False
        mock_exists.side_effect = mock_exists_side_effect
        mock_get_cache_path.return_value = "cache/hashed_file.wav"
        
        # We mock open() to simulate reading the generated file for caching
        with patch("builtins.open", unittest.mock.mock_open(read_data=b"audio data")):
            result = generate_audio("Hello", "output.mp3")
            
            self.assertTrue(result)
            mock_async_run.assert_called() # Generation happened
            mock_save_to_cache.assert_called() # Saved to cache

if __name__ == '__main__':
    unittest.main()
