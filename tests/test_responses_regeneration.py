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
    def test_regeneration_retries_when_response_is_duplicate(
        self,
        mock_ollama_chat,
        mock_memory_manager,
        mock_get_setting,
        _mock_build_system_prompt,
        _mock_get_sentiment,
        _mock_call_once,
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
        mock_ollama_chat.return_value = [{"message": {"content": "Old answer"}}]

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
        self.assertEqual(last_msg["content"], "Different response path")
        self.assertEqual(last_msg["alternatives"], ["Old answer", "Different response path"])


if __name__ == "__main__":
    unittest.main()
