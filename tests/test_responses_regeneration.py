import unittest
from unittest.mock import patch

from engines.responses import get_respond_stream


class TestResponsesRegeneration(unittest.TestCase):
    @patch("engines.responses.get_pipeline_flags", return_value={
        "enabled": False,
        "instrumentation": False,
        "state": False,
        "memory": False,
        "planner": False,
        "candidates": False,
        "critic": False,
        "candidate_count": 1,
        "style_profile": "balanced",
    })
    @patch("engines.responses.get_sentiment_score", return_value=0)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM_PROMPT")
    @patch("engines.responses.get_setting")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.ollama.chat")
    def test_regeneration_excludes_last_assistant_from_prompt(
        self,
        mock_ollama_chat,
        mock_memory_manager,
        mock_get_setting,
        _mock_build_system_prompt,
        _mock_get_sentiment,
        _mock_pipeline_flags,
    ):
        profile = {"name": "TestAI", "llm_model": "test-model", "relationship_score": 0}
        prompt_history = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Old answer"},
        ]
        full_history = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Old answer"},
        ]

        mock_get_setting.side_effect = lambda key, default=None: {
            "default_llm_model": "test-model",
            "remote_llm_url": None,
            "interaction_mode": "rp",
            "memory_limit": 15,
        }.get(key, default)
        mock_memory_manager.get_full_data.return_value = {
            "metadata": {"current_scene": "Room", "memory_core": ""}
        }
        mock_memory_manager.load_history.side_effect = [prompt_history, full_history]
        mock_ollama_chat.return_value = [{"message": {"content": "New answer"}}]

        list(
            get_respond_stream(
                "Question",
                profile,
                history_profile_name="test_profile",
                is_regeneration=True,
            )
        )

        llm_messages = mock_ollama_chat.call_args_list[0][1]["messages"]
        self.assertEqual(llm_messages[0]["role"], "system")
        self.assertEqual(llm_messages[1:], [{"role": "user", "content": "Question"}])

    @patch("engines.responses.get_pipeline_flags", return_value={
        "enabled": False,
        "instrumentation": False,
        "state": False,
        "memory": False,
        "planner": False,
        "candidates": False,
        "critic": False,
        "candidate_count": 1,
        "style_profile": "balanced",
    })
    @patch("engines.responses.get_sentiment_score", return_value=0)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM_PROMPT")
    @patch("engines.responses.get_setting")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.ollama.chat")
    def test_regeneration_updates_alternatives_and_selected_index(
        self,
        mock_ollama_chat,
        mock_memory_manager,
        mock_get_setting,
        _mock_build_system_prompt,
        mock_get_sentiment,
        _mock_pipeline_flags,
    ):
        profile = {"name": "TestAI", "llm_model": "test-model", "relationship_score": 0}
        prompt_history = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Old answer"},
        ]
        full_history = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Old answer"},
        ]

        mock_get_setting.side_effect = lambda key, default=None: {
            "default_llm_model": "test-model",
            "remote_llm_url": None,
            "interaction_mode": "rp",
            "memory_limit": 15,
        }.get(key, default)
        mock_memory_manager.get_full_data.return_value = {
            "metadata": {"current_scene": "Room", "memory_core": ""}
        }
        mock_memory_manager.load_history.side_effect = [prompt_history, full_history]
        mock_ollama_chat.return_value = [{"message": {"content": "Regenerated answer"}}]

        list(
            get_respond_stream(
                "Question",
                profile,
                history_profile_name="test_profile",
                is_regeneration=True,
            )
        )

        saved_history = mock_memory_manager.save_history.call_args[0][1]
        last_msg = saved_history[-1]

        self.assertEqual(len(saved_history), 2)
        self.assertEqual(last_msg["alternatives"], ["Old answer", "Regenerated answer"])
        self.assertEqual(last_msg["selected_index"], 1)
        self.assertEqual(last_msg["content"], "Regenerated answer")
        mock_get_sentiment.assert_not_called()

    @patch("engines.responses.get_pipeline_flags", return_value={
        "enabled": False,
        "instrumentation": False,
        "state": False,
        "memory": False,
        "planner": False,
        "candidates": False,
        "critic": False,
        "candidate_count": 1,
        "style_profile": "balanced",
    })
    @patch("engines.responses._call_llm_once", return_value="Different response path")
    @patch("engines.responses.get_sentiment_score", return_value=0)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM_PROMPT")
    @patch("engines.responses.get_setting")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.ollama.chat")
    def test_regeneration_skips_retry_in_live_streaming_mode(
        self,
        mock_ollama_chat,
        mock_memory_manager,
        mock_get_setting,
        _mock_build_system_prompt,
        _mock_get_sentiment,
        mock_call_once,
        _mock_pipeline_flags,
    ):
        """Verify that live streaming (pipeline off) skips the diversity retry logic."""
        profile = {"name": "TestAI", "llm_model": "test-model", "relationship_score": 0}
        prompt_history = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Old answer"},
        ]
        full_history = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Old answer", "alternatives": ["Old answer"], "selected_index": 0},
        ]

        mock_get_setting.side_effect = lambda key, default=None: {
            "default_llm_model": "test-model",
            "remote_llm_url": None,
            "interaction_mode": "rp",
            "memory_limit": 15,
        }.get(key, default)
        mock_memory_manager.get_full_data.return_value = {
            "metadata": {"current_scene": "Room", "memory_core": ""}
        }
        mock_memory_manager.load_history.side_effect = [prompt_history, full_history]
        mock_ollama_chat.return_value = [{"message": {"content": "Duplicate response"}}]

        list(
            get_respond_stream(
                "Question",
                profile,
                history_profile_name="test_profile",
                is_regeneration=True,
            )
        )

        # Verification:
        # 1. Diversity retry path (_call_llm_once) MUST NOT be called in live streaming
        mock_call_once.assert_not_called()
        
        # 2. Bookkeeping SHOULD still happen (new alternative added)
        saved_history = mock_memory_manager.save_history.call_args[0][1]
        last_msg = saved_history[-1]
        self.assertEqual(len(last_msg["alternatives"]), 2)
        self.assertEqual(last_msg["selected_index"], 1)
        self.assertEqual(last_msg["content"], "Duplicate response")

    @patch("engines.responses.get_pipeline_flags", return_value={
        "enabled": True,
        "instrumentation": False,
        "state": False,
        "memory": False,
        "planner": False,
        "candidates": True,
        "critic": False,
        "candidate_count": 1,
        "style_profile": "balanced",
    })
    @patch("engines.responses._generate_candidate_replies")
    @patch("engines.responses.get_sentiment_score", return_value=0)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM_PROMPT")
    @patch("engines.responses.get_setting")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.ollama.chat")
    def test_regeneration_uses_streaming_path_when_candidate_count_is_one(
        self,
        mock_ollama_chat,
        mock_memory_manager,
        mock_get_setting,
        _mock_build_system_prompt,
        _mock_get_sentiment,
        mock_gen_candidates,
        _mock_pipeline_flags,
    ):
        """Verify that candidate_count=1 forces the real streaming path even if pipeline is enabled."""
        profile = {"name": "TestAI", "llm_model": "test-model", "relationship_score": 0}
        prompt_history = [{"role": "user", "content": "Hi"}]
        full_history = [{"role": "user", "content": "Hi"}]

        mock_get_setting.side_effect = lambda key, default=None: {
            "default_llm_model": "test-model",
            "remote_llm_url": None,
            "interaction_mode": "rp",
            "memory_limit": 15,
        }.get(key, default)
        mock_memory_manager.get_full_data.return_value = {
            "metadata": {"current_scene": "Room", "memory_core": ""}
        }
        mock_memory_manager.load_history.side_effect = [prompt_history, full_history]
        mock_ollama_chat.return_value = [{"message": {"content": "Streamed response"}}]

        list(get_respond_stream("Hi", profile, is_regeneration=True))

        # Real streaming uses ollama.chat directly
        mock_ollama_chat.assert_called()
        # Candidate generation should NOT be called
        mock_gen_candidates.assert_not_called()

    @patch("engines.responses.get_pipeline_flags", return_value={
        "enabled": False,
        "instrumentation": False,
        "state": False,
        "memory": False,
        "planner": False,
        "candidates": False,
        "critic": False,
        "candidate_count": 1,
        "style_profile": "balanced",
    })
    @patch("engines.responses.get_sentiment_score", return_value=0)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM_PROMPT")
    @patch("engines.responses.get_setting")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.ollama.chat")
    def test_regeneration_on_failed_turn_saves_both_messages(
        self,
        mock_ollama_chat,
        mock_memory_manager,
        mock_get_setting,
        _mock_build_system_prompt,
        mock_get_sentiment,
        _mock_pipeline_flags,
    ):
        """Verify that when regenerating a failed turn, it acts like a normal first-time message turn."""
        profile = {"name": "TestAI", "llm_model": "test-model", "relationship_score": 0}
        # prompt_history doesn't contain "Hi"
        prompt_history = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
        ]
        full_history = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
        ]

        mock_get_setting.side_effect = lambda key, default=None: {
            "default_llm_model": "test-model",
            "remote_llm_url": None,
            "interaction_mode": "rp",
            "memory_limit": 15,
        }.get(key, default)
        mock_memory_manager.get_full_data.return_value = {
            "metadata": {"current_scene": "Room", "memory_core": ""}
        }
        mock_memory_manager.load_history.side_effect = [prompt_history, full_history]
        mock_ollama_chat.return_value = [{"message": {"content": "New response"}}]

        # Trigger generation for "Hi" with is_regeneration=True
        # Since prompt_history doesn't contain "Hi" as the last user turn before assistant,
        # it should treat it as is_regeneration=False internally.
        list(
            get_respond_stream(
                "Hi",
                profile,
                history_profile_name="test_profile",
                is_regeneration=True,
            )
        )

        # It should save BOTH the user input "Hi" and the assistant response "New response" to history
        saved_history = mock_memory_manager.save_history.call_args[0][1]
        self.assertEqual(len(saved_history), 4)
        self.assertEqual(saved_history[2], {"role": "user", "content": "Hi"})
        self.assertEqual(saved_history[3], {"role": "assistant", "content": "New response"})
        mock_get_sentiment.assert_called_once()
        mock_memory_manager.clear_pending_user_message.assert_called_once_with("test_profile")


if __name__ == "__main__":
    unittest.main()
