import unittest
from unittest.mock import patch
import os
import sys

# Add the project root to sys.path to import engines
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestXTTSLocal(unittest.TestCase):

    @patch('engines.xtts_local.XTTS_AVAILABLE', True)
    @patch('engines.xtts_local.TTS')
    def test_xtts_initialization(self, mock_tts):
        from engines.xtts_local import XTTSWorker
        # Reset singleton for testing
        XTTSWorker._instance = None
        XTTSWorker._model = None
        
        worker = XTTSWorker()
        # Verify it attempts to load the model
        self.assertTrue(mock_tts.called)

    @patch('engines.xtts_local.XTTS_AVAILABLE', True)
    @patch('engines.xtts_local.TTS')
    def test_generate_audio_local(self, mock_tts):
        from engines.xtts_local import XTTSWorker
        # Reset singleton for testing
        XTTSWorker._instance = None
        XTTSWorker._model = None
        
        mock_instance = mock_tts.return_value
        # Mocking the .to("cuda") call
        mock_instance.to.return_value = mock_instance
        
        worker = XTTSWorker()
        result = worker.generate("Hello world", "output.wav", "voices/ref.wav")
        
        # Verify it calls tts_to_file
        mock_instance.tts_to_file.assert_called()
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
