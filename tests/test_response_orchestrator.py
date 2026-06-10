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
            "smooth_streaming": False,
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
            "smooth_streaming": False,
        }.get(key, default)

        events = list(iterate_response_events("hi", {"tts_language": "en"}, "profile"))
        tts_events = [e for e in events if e["type"] == "tts"]
        self.assertTrue(tts_events)
        self.assertEqual(events[-1]["type"], "complete")

    @patch("engines.response_orchestrator.clean_text_for_tts", side_effect=lambda text, speak_narration=True: text.strip())
    @patch("engines.response_orchestrator.get_respond_stream", return_value=iter(["Hello. ", "World."]))
    @patch("engines.response_orchestrator.get_setting")
    def test_tts_master_toggle_applies_mid_stream(self, mock_get_setting, _mock_stream, _mock_clean):
        tts_calls = {"count": 0}

        def setting_side_effect(key, default=None):
            if key == "tts_enabled":
                tts_calls["count"] += 1
                return tts_calls["count"] == 1
            values = {
                "character_speak": True,
                "narration_tts_voice": "en-US-AndrewNeural",
                "speak_narration": True,
                "smooth_streaming": False,
            }
            return values.get(key, default)

        mock_get_setting.side_effect = setting_side_effect
        events = list(iterate_response_events("hi", {"tts_language": "en"}, "profile"))
        tts_events = [event for event in events if event["type"] == "tts"]
        self.assertEqual(len(tts_events), 1)
        self.assertEqual(events[-1]["type"], "complete")

    @patch("engines.response_orchestrator.get_respond_stream", return_value=iter(["Hey", "you"]))
    @patch("engines.response_orchestrator.get_setting")
    def test_iterate_response_events_smooth_streaming_enabled(self, mock_get_setting, _mock_stream):
        mock_get_setting.side_effect = lambda key, default=None: {
            "tts_enabled": False,
            "smooth_streaming": True,
            "streaming_delay": 0.0,
        }.get(key, default)

        events = list(iterate_response_events("hi", {}, "profile"))
        chunk_events = [e for e in events if e["type"] == "chunk"]
        
        # "Heyyou" has 6 characters. Typewriter mode yields them step by step.
        # It should yield them character by character or in small chunks.
        self.assertGreater(len(chunk_events), 2)
        
        # Verify sequence of chunk event payloads builds up correctly
        responses = [e["full_response"] for e in chunk_events]
        self.assertEqual(responses[-1], "Heyyou")
        self.assertEqual(responses[0], "H")
        
        # Ensure completion payload matches
        self.assertEqual(events[-1]["type"], "complete")
        self.assertEqual(events[-1]["full_response"], "Heyyou")

    @patch("engines.response_orchestrator.get_respond_stream", return_value=iter(["Hey", "you"]))
    @patch("engines.response_orchestrator.get_setting")
    def test_iterate_response_events_smooth_streaming_disabled(self, mock_get_setting, _mock_stream):
        mock_get_setting.side_effect = lambda key, default=None: {
            "tts_enabled": False,
            "smooth_streaming": False,
        }.get(key, default)

        events = list(iterate_response_events("hi", {}, "profile"))
        chunk_events = [e for e in events if e["type"] == "chunk"]
        
        # Instant stream mode should only yield 2 chunks (one for each stream item)
        self.assertEqual(len(chunk_events), 2)
        self.assertEqual(chunk_events[0]["full_response"], "Hey")
        self.assertEqual(chunk_events[1]["full_response"], "Heyyou")
        
        self.assertEqual(events[-1]["type"], "complete")
        self.assertEqual(events[-1]["full_response"], "Heyyou")


if __name__ == "__main__":
    unittest.main()

