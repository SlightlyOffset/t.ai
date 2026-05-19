import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tempfile

# Add the project root to sys.path to import engines
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestXTTSRemote(unittest.TestCase):
    def setUp(self):
        # Clear the uploaded voices cache for test isolation
        from engines.xtts_remote import _UPLOADED_VOICES
        _UPLOADED_VOICES.clear()

    @patch('engines.xtts_remote.requests.get')
    @patch('engines.xtts_remote.requests.post')
    @patch('engines.xtts_remote.get_setting')
    def test_generate_audio_remote_success(self, mock_get_setting, mock_post, mock_get):
        from engines.xtts_remote import generate_remote_xtts
        mock_get_setting.side_effect = lambda k, d=None: "https://mock-bridge.ngrok.app" if k == "remote_tts_url" else d
        
        # Mock ping and check_speaker (requests.get)
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {"exists": True}
        mock_get.return_value = mock_get_resp

        # Mock successful response with binary content (requests.post)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b"fake-audio-data"]
        mock_post.return_value.__enter__.return_value = mock_response
        
        # We need a dummy reference file for the test
        with open("dummy_ref.wav", "wb") as f: f.write(b"dummy")
        
        result = generate_remote_xtts("Hello", "output.wav", "dummy_ref.wav")
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists("output.wav"))
        
        # Cleanup
        if os.path.exists("output.wav"): os.remove("output.wav")
        if os.path.exists("dummy_ref.wav"): os.remove("dummy_ref.wav")

    @patch('engines.xtts_remote.get_setting')
    def test_generate_remote_fails_without_url(self, mock_get_setting):
        from engines.xtts_remote import generate_remote_xtts
        mock_get_setting.return_value = None
        
        result = generate_remote_xtts("Hello", "output.wav", "ref.wav")
        self.assertFalse(result)

    @patch('engines.xtts_remote.save_pcm_as_wav')
    @patch('engines.xtts_remote.requests.post')
    @patch('engines.xtts_remote.ensure_voice_on_bridge')
    @patch('engines.xtts_remote.get_setting')
    @patch('engines.xtts_remote._get_speaker_id')
    def test_generate_remote_retries_once_on_404_with_force_reupload(
        self,
        mock_get_speaker_id,
        mock_get_setting,
        mock_ensure_voice_on_bridge,
        mock_post,
        mock_save_pcm_as_wav,
    ):
        from engines.xtts_remote import generate_remote_xtts, _UPLOADED_VOICES

        mock_get_speaker_id.return_value = "speaker-a"
        mock_get_setting.side_effect = lambda k, d=None: "https://mock-bridge.ngrok.app" if k == "remote_tts_url" else d
        mock_ensure_voice_on_bridge.return_value = True

        first_resp = MagicMock()
        first_resp.status_code = 404
        first_resp.text = "speaker not found"

        second_resp = MagicMock()
        second_resp.status_code = 200
        second_resp.iter_content.return_value = [b"fake-audio-data"]

        first_ctx = MagicMock()
        first_ctx.__enter__.return_value = first_resp
        second_ctx = MagicMock()
        second_ctx.__enter__.return_value = second_resp
        mock_post.side_effect = [first_ctx, second_ctx]

        _UPLOADED_VOICES.add("speaker-a")
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_ref = os.path.join(tmp_dir, "ref.wav")
            output_wav = os.path.join(tmp_dir, "out.wav")
            with open(dummy_ref, "wb") as f:
                f.write(b"dummy")

            result = generate_remote_xtts("Hello", output_wav, dummy_ref)

        self.assertTrue(result)
        self.assertNotIn("speaker-a", _UPLOADED_VOICES)
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_ensure_voice_on_bridge.call_count, 2)
        self.assertEqual(mock_ensure_voice_on_bridge.call_args_list[0].kwargs.get("force"), False)
        self.assertEqual(mock_ensure_voice_on_bridge.call_args_list[1].kwargs.get("force"), True)
        mock_save_pcm_as_wav.assert_called_once()

if __name__ == '__main__':
    unittest.main()
