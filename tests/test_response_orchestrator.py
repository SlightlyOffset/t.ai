import unittest
from unittest.mock import patch

from engines.response_orchestrator import iterate_response_events


class TestResponseOrchestrator(unittest.TestCase):
    @patch("engines.response_orchestrator.get_respond_stream", return_value=iter(["Hello ", "world!"]))
    @patch("engines.response_orchestrator.get_setting")
    def test_iterate_response_events_without_tts(self, mock_get_setting, _mock_stream):
        mock_get_setting.side_effect = lambda key, default=None: {
            "tts_enabled": False,
            "character_speak": False,
            "narration_tts_voice": "en-US-AndrewNeural",
            "speak_narration": False,
        }.get(key, default)

        events = list(iterate_response_events("hi", {}, "profile"))
        chunk_events = [e for e in events if e["type"] == "chunk"]
        self.assertEqual(len(chunk_events), 2)
        self.assertEqual(events[-1]["type"], "complete")
        self.assertEqual(events[-1]["full_response"], "Hello world!")

    @patch("engines.response_orchestrator.clean_text_for_tts", side_effect=lambda text, speak_narration=True: text.strip())
    @patch("engines.response_orchestrator.get_respond_stream", return_value=iter(["Hi. ", "*Act* done."]))
    @patch("engines.response_orchestrator.get_setting")
    def test_iterate_response_events_with_tts(self, mock_get_setting, _mock_stream, _mock_clean):
        mock_get_setting.side_effect = lambda key, default=None: {
            "tts_enabled": True,
            "character_speak": True,
            "narration_tts_voice": "en-US-AndrewNeural",
            "speak_narration": True,
        }.get(key, default)

        events = list(iterate_response_events("hi", {"tts_language": "en"}, "profile"))
        tts_events = [e for e in events if e["type"] == "tts"]
        self.assertTrue(tts_events)
        self.assertEqual(events[-1]["type"], "complete")


if __name__ == "__main__":
    unittest.main()
