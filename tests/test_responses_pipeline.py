import unittest
from unittest.mock import MagicMock, patch

from engines.responses import _call_llm_once, get_respond_stream


class TestResponsesPipeline(unittest.TestCase):
    @patch("engines.responses.requests.post")
    def test_call_llm_once_remote_plain_text_fallback(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("not json")
        mock_response.text = "Plain text remote reply"
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        reply = _call_llm_once(
            messages=[{"role": "user", "content": "Hi"}],
            model="test-model",
            remote_url="https://bridge.example",
        )

        self.assertEqual(reply, "Plain text remote reply")
        mock_post.assert_called_once()

    @patch("engines.responses.requests.post")
    def test_call_llm_once_remote_json_choices(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "JSON remote reply"}}]
        }
        mock_response.text = ""
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        reply = _call_llm_once(
            messages=[{"role": "user", "content": "Hi"}],
            model="test-model",
            remote_url="https://bridge.example",
        )

        self.assertEqual(reply, "JSON remote reply")
        mock_post.assert_called_once()

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

    @patch("engines.responses.get_sentiment_score", return_value=0)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM")
    @patch("engines.responses.scan_for_lore", return_value="")
    @patch("engines.responses.load_lorebook", return_value={})
    @patch("engines.responses._generate_candidate_replies", return_value=['"Old answer"', '"Different answer"'])
    @patch("engines.responses.get_pipeline_flags")
    @patch("engines.responses.rank_candidates")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.get_setting")
    def test_regen_candidates_skip_duplicate_top_choice(
        self,
        mock_get_setting,
        mock_memory_manager,
        mock_rank_candidates,
        mock_get_pipeline_flags,
        _mock_candidates,
        _mock_lorebook,
        _mock_scan,
        _mock_build_prompt,
        _mock_sentiment,
    ):
        profile = {"name": "TestAI", "llm_model": "test-model", "relationship_score": 0}
        prompt_history = [
            {"role": "user", "content": "Question"},
            {
                "role": "assistant",
                "content": "Old answer",
                "alternatives": ["Old answer"],
                "selected_index": 0,
            },
        ]
        full_history = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Old answer", "alternatives": ["Old answer"], "selected_index": 0},
        ]
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
            "memory": False,
            "planner": False,
            "candidates": True,
            "critic": False,
            "candidate_count": 2,
            "style_profile": "balanced",
        }
        mock_memory_manager.get_full_data.return_value = full_data
        mock_memory_manager.load_history.side_effect = [prompt_history, full_history]
        mock_rank_candidates.return_value = [
            {"index": 0, "text": "Old answer", "metrics": {"total": 9.5}},
            {"index": 1, "text": "Different answer", "metrics": {"total": 9.0}},
        ]

        chunks = list(get_respond_stream("Question", profile, history_profile_name="test_profile", is_regeneration=True))
        combined = "".join(chunks)
        self.assertIn("Different answer", combined)

        saved_history = mock_memory_manager.save_history.call_args[0][1]
        last_msg = saved_history[-1]
        self.assertEqual(last_msg["content"], "Different answer")
        self.assertEqual(last_msg["alternatives"], ["Old answer", "Different answer"])

    @patch("engines.responses.get_sentiment_score", return_value=0)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM")
    @patch("engines.responses.scan_for_lore", return_value="")
    @patch("engines.responses.load_lorebook", return_value={})
    @patch("engines.responses._generate_candidate_replies")
    @patch("engines.responses._call_llm_once", return_value='Single pass reply')
    @patch("engines.responses.get_pipeline_flags")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.get_setting")
    def test_critic_only_mode_skips_multi_candidate_generation(
        self,
        mock_get_setting,
        mock_memory_manager,
        mock_get_pipeline_flags,
        mock_call_once,
        mock_generate_candidates,
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
            "memory": False,
            "planner": False,
            "candidates": False,
            "critic": True,
            "candidate_count": 3,
            "style_profile": "balanced",
        }

        mock_memory_manager.get_full_data.return_value = full_data
        mock_memory_manager.load_history.side_effect = [history, list(history)]

        chunks = list(get_respond_stream("Hi", profile, history_profile_name="test_profile", is_regeneration=False))
        self.assertIn("Single pass reply", "".join(chunks))
        mock_generate_candidates.assert_not_called()
        mock_call_once.assert_called()

    @patch("engines.responses.get_sentiment_score", return_value=1)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM")
    @patch("engines.responses.scan_for_lore", return_value="")
    @patch("engines.responses.load_lorebook", return_value={})
    @patch("engines.responses._generate_candidate_replies", return_value=[])
    @patch("engines.responses.get_pipeline_flags")
    @patch("engines.responses.rank_candidates")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.get_setting")
    @patch("engines.responses.requests.post")
    def test_pipeline_remote_candidate_fallback_uses_plain_text_bridge(
        self,
        mock_post,
        mock_get_setting,
        mock_memory_manager,
        mock_rank_candidates,
        mock_get_pipeline_flags,
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
            "remote_llm_url": "https://bridge.example",
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
                "index": 0,
                "text": "Remote candidate reply",
                "metrics": {
                    "total": 9.0,
                    "in_character": 9,
                    "narrative_progression": 9,
                    "continuity": 9,
                    "style": 9,
                },
            }
        ]

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("not json")
        mock_response.text = "Remote candidate reply"
        mock_post.return_value = mock_response

        chunks = list(get_respond_stream("Hi", profile, history_profile_name="test_profile", is_regeneration=False))
        self.assertIn("Remote candidate reply", "".join(chunks))
        self.assertTrue(mock_post.called)


if __name__ == "__main__":
    unittest.main()
