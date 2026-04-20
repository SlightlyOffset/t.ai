import unittest
from unittest.mock import patch

from engines.responses import get_respond_stream


class TestResponsesPipeline(unittest.TestCase):
    @patch("engines.responses.get_sentiment_score", return_value=1)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM")
    @patch("engines.responses.scan_for_lore", return_value="")
    @patch("engines.responses.load_lorebook", return_value={})
    @patch("engines.responses._generate_candidate_replies", return_value=['"Reply one."', '"Reply two."'])
    @patch("engines.responses._call_llm_once", return_value='"Fallback reply."')
    @patch("engines.responses.get_pipeline_flags")
    @patch("engines.responses.rank_candidates")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.get_setting")
    def test_pipeline_candidates_path(
        self,
        mock_get_setting,
        mock_memory_manager,
        mock_rank_candidates,
        mock_get_pipeline_flags,
        _mock_call_once,
        _mock_candidates,
        _mock_lorebook,
        _mock_scan,
        _mock_build_prompt,
        _mock_sentiment,
    ):
        profile = {"name": "TestAI", "llm_model": "test-model", "relationship_score": 0}
        history = [{"role": "user", "content": "Hello"}]
        full_data = {"metadata": {"current_scene": "Room", "memory_core": "", "narrative_state": {}}}

        mock_get_setting.side_effect = lambda key, default=None: {
            "default_llm_model": "test-model",
            "remote_llm_url": None,
            "interaction_mode": "rp",
            "memory_limit": 15,
        }.get(key, default)
        mock_get_pipeline_flags.return_value = {
            "enabled": True,
            "instrumentation": False,
            "state": True,
            "memory": True,
            "planner": True,
            "candidates": True,
            "critic": False,
            "candidate_count": 2,
            "style_profile": "balanced",
        }

        mock_memory_manager.get_full_data.return_value = full_data
        mock_memory_manager.load_history.side_effect = [history, history, list(history)]
        mock_rank_candidates.return_value = [
            {
                "index": 1,
                "text": '"Reply two."',
                "metrics": {
                    "total": 9.0,
                    "in_character": 9,
                    "narrative_progression": 9,
                    "continuity": 9,
                    "style": 9,
                },
            }
        ]

        chunks = list(get_respond_stream("Hi", profile, history_profile_name="test_profile", is_regeneration=False))
        combined = "".join(chunks)
        self.assertIn("Reply two.", combined)
        self.assertTrue(mock_memory_manager.save_history.called)
        self.assertTrue(mock_memory_manager.update_narrative_state.called)


if __name__ == "__main__":
    unittest.main()
