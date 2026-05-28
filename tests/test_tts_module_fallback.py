import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the project root to sys.path to import engines
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engines.tts_module import generate_audio

class TestTTSModuleFallback(unittest.TestCase):

    @patch('engines.tts_module.is_xtts_supported')
    @patch('engines.tts_module.XTTSWorker')
    @patch('engines.tts_module.asyncio.run')
    @patch('engines.tts_module.generate_edge_tts', new_callable=MagicMock)
    @patch('engines.tts_module.EDGE_AVAILABLE', True)
    @patch('engines.tts_module.is_online')
    @patch('engines.tts_module.get_setting')
    @patch('engines.tts_module.os.path.exists')
    def test_generate_audio_fallback_to_edge_on_xtts_failure(self, mock_exists, mock_get_setting, mock_is_online, mock_generate_edge, mock_async_run, mock_xtts_worker, mock_is_xtts_supported):
        mock_get_setting.side_effect = lambda k, d=None: True if k == "tts_enabled" else ("en-GB-SoniaNeural" if k == "default_tts_voice" else d)
        mock_is_online.return_value = True
        
        # Robust path check: cache should miss, filename should exist
        def exists_side_effect(path):
            if "cache" in str(path): return False
            return True
        mock_exists.side_effect = exists_side_effect
        
        # Mock XTTSWorker to fail
        mock_worker_instance = mock_xtts_worker.return_value
        mock_worker_instance.generate.return_value = False
        
        # Mock open for reading the generated file to save to cache
        with patch("builtins.open", unittest.mock.mock_open(read_data=b"audio data")):
            # Call generate_audio with engine="xtts"
            result = generate_audio("Hello", "test.mp3", engine="xtts", clone_ref="voices/ref.wav")
            
            # Verify it attempted XTTS but ultimately succeeded via Edge-TTS fallback
            self.assertTrue(mock_worker_instance.generate.called)
            self.assertTrue(mock_async_run.called) # Edge-TTS called
            self.assertTrue(result)

    @patch('engines.tts_module.is_xtts_supported')
    @patch('engines.tts_module.XTTSWorker')
    @patch('engines.tts_module.asyncio.run')
    @patch('engines.tts_module.generate_edge_tts', new_callable=MagicMock)
    @patch('engines.tts_module.is_online')
    @patch('engines.tts_module.get_setting')
    @patch('engines.tts_module.os.path.exists')
    def test_generate_audio_fallback_to_edge_when_xtts_not_supported(self, mock_exists, mock_get_setting, mock_is_online, mock_generate_edge, mock_async_run, mock_xtts_worker, mock_is_xtts_supported):
        mock_get_setting.side_effect = lambda k, d=None: True if k == "tts_enabled" else d
        mock_is_xtts_supported.return_value = False
        mock_is_online.return_value = True
        
        def exists_side_effect(path):
            if "cache" in str(path): return False
            return True
        mock_exists.side_effect = exists_side_effect
        
        # Mock open for reading the generated file to save to cache
        with patch("builtins.open", unittest.mock.mock_open(read_data=b"audio data")):
            # Call generate_audio with engine="xtts"
            result = generate_audio("Hello", "test.mp3", engine="xtts", clone_ref="voices/ref.wav")
            
            # Verify it skipped XTTS and used Edge-TTS
            self.assertFalse(mock_xtts_worker.called)
            self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
