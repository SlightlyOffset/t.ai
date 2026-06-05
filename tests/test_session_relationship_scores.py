import unittest
import os
import sys
import json
import shutil
from unittest.mock import patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engines.responses import get_respond_stream
from engines.memory_v2 import HistoryManager
from engines.app_commands import app_commands


class TestSessionRelationshipScores(unittest.TestCase):
    def setUp(self):
        # Force background threads to run synchronously during tests
        self.thread_patcher = patch("threading.Thread.start", autospec=True)
        self.mock_thread_start = self.thread_patcher.start()

        def run_sync(mock_self):
            if mock_self._target:
                mock_self._target(*mock_self._args, **mock_self._kwargs)

        self.mock_thread_start.side_effect = run_sync

        self.test_dir = "test_history_rel"
        self.manager = HistoryManager(history_dir=self.test_dir)
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)

        # Patch memory_manager in responses.py and app_commands.py to use our test manager
        self.patch_responses_manager = patch(
            "engines.responses.memory_manager", self.manager
        )
        self.patch_commands_manager = patch(
            "engines.app_commands.memory_manager", self.manager
        )
        self.patch_responses_manager.start()
        self.patch_commands_manager.start()

    def tearDown(self):
        self.thread_patcher.stop()
        self.patch_responses_manager.stop()
        self.patch_commands_manager.stop()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch(
        "engines.responses.get_pipeline_flags",
        return_value={
            "enabled": False,
            "instrumentation": False,
            "state": False,
            "memory": False,
            "planner": False,
            "candidates": False,
            "critic": False,
            "candidate_count": 1,
            "style_profile": "balanced",
        },
    )
    @patch("engines.responses.get_sentiment_score", return_value=3)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM_PROMPT")
    @patch("engines.responses.get_setting")
    @patch("engines.responses.ollama.chat")
    def test_relationship_score_stored_in_session_not_profile(
        self,
        mock_ollama_chat,
        mock_get_setting,
        _mock_build_system_prompt,
        _mock_get_sentiment,
        _mock_pipeline_flags,
    ):
        # 1. Prepare read-only profile template in dict
        profile = {
            "name": "TestAI",
            "llm_model": "test-model",
            "relationship_score": 10,  # baseline relationship score
        }

        mock_get_setting.side_effect = lambda key, default=None: {
            "default_llm_model": "test-model",
            "remote_llm_url": None,
            "interaction_mode": "rp",
            "memory_limit": 15,
        }.get(key, default)

        mock_ollama_chat.return_value = [{"message": {"content": "Hello user"}}]

        # Write dummy profiles/TestAI.json to temp folder or patch open?
        # Let's write the profile card JSON file to profiles/TestAI.json to verify it remains unchanged
        os.makedirs("profiles", exist_ok=True)
        profile_path = "profiles/TestAI.json"
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=4)

        try:
            # 2. Run respond stream (first turn)
            # No history exists, so it should fall back to profile baseline relationship_score (10).
            # Sentiment returns +3.
            # The new score should be 10 + 3 = 13.
            list(
                get_respond_stream(
                    "Hello companion",
                    profile,
                    profile_path=profile_path,
                    history_profile_name="TestAI",
                )
            )

            # Check that the session history file was saved with the updated score 12.7
            data = self.manager.get_full_data("TestAI")
            self.assertEqual(data["metadata"]["relationship_score"], 12.7)

            # Check that the base profile JSON on disk remained UNCHANGED (10)
            with open(profile_path, "r", encoding="utf-8") as f:
                disk_profile = json.load(f)
            self.assertEqual(disk_profile["relationship_score"], 10)

            # 3. Run respond stream again (second turn)
            # Since history exists, it should load the score from metadata (12.7).
            # Sentiment returns +3. New score should be 12.7 + damped(+3) = 15.32.
            # We mock the chat to return another message.
            mock_ollama_chat.reset_mock()
            mock_ollama_chat.return_value = [
                {"message": {"content": "Hello user again"}}
            ]

            list(
                get_respond_stream(
                    "Hello companion again",
                    profile,
                    profile_path=profile_path,
                    history_profile_name="TestAI",
                )
            )

            # Check that the session history file was saved with the updated score 15.32
            data = self.manager.get_full_data("TestAI")
            self.assertEqual(data["metadata"]["relationship_score"], 15.32)

            # Check that the base profile JSON on disk still remained UNCHANGED (10)
            with open(profile_path, "r", encoding="utf-8") as f:
                disk_profile = json.load(f)
            self.assertEqual(disk_profile["relationship_score"], 10)

        finally:
            if os.path.exists(profile_path):
                os.remove(profile_path)

    @patch("engines.app_commands.get_setting")
    def test_reset_rel_resets_session_score_not_profile(self, mock_get_setting):
        profile = {"name": "TestAI", "relationship_score": 50}
        os.makedirs("profiles", exist_ok=True)
        profile_path = "profiles/TestAI.json"
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=4)

        try:
            # Save history with relationship score = 30
            self.manager.save_history(
                "TestAI", [{"role": "user", "content": "Hi"}], relationship_score=30
            )

            # Setup command mock settings
            mock_get_setting.return_value = "TestAI.json"

            # Run the command //reset rel
            app_commands("//reset rel", suppress_output=True)

            # Verify session history score is reset to 0
            data = self.manager.get_full_data("TestAI")
            self.assertEqual(data["metadata"]["relationship_score"], 0)

            # Verify profile card JSON remains unchanged at 50
            with open(profile_path, "r", encoding="utf-8") as f:
                disk_profile = json.load(f)
            self.assertEqual(disk_profile["relationship_score"], 50)

        finally:
            if os.path.exists(profile_path):
                os.remove(profile_path)

    def test_new_session_pulls_baseline_score(self):
        profile = {"name": "TestAI", "relationship_score": 77}
        os.makedirs("profiles", exist_ok=True)
        profile_path = "profiles/TestAI.json"
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=4)

        try:
            # Save history with default relationship_score=None
            self.manager.save_history("TestAI", [], session_name="new_route")

            # Verify new session history score is pulled from profile baseline (77)
            data = self.manager.get_full_data("TestAI", session_name="new_route")
            self.assertEqual(data["metadata"]["relationship_score"], 77)

        finally:
            if os.path.exists(profile_path):
                os.remove(profile_path)

    def test_save_history_preserves_existing_score_if_not_specified(self):
        profile = {"name": "TestAI", "relationship_score": 77}
        os.makedirs("profiles", exist_ok=True)
        profile_path = "profiles/TestAI.json"
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=4)

        try:
            # 1. Create a session and set score to 42
            self.manager.save_history(
                "TestAI", [], relationship_score=42, session_name="active_sess"
            )
            data = self.manager.get_full_data("TestAI", session_name="active_sess")
            self.assertEqual(data["metadata"]["relationship_score"], 42)

            # 2. Save history with relationship_score=None (i.e. not specified)
            self.manager.save_history(
                "TestAI",
                [{"role": "user", "content": "hi"}],
                session_name="active_sess",
            )

            # 3. Verify it preserved the 42 score instead of resetting to baseline (77)
            data = self.manager.get_full_data("TestAI", session_name="active_sess")
            self.assertEqual(data["metadata"]["relationship_score"], 42)

        finally:
            if os.path.exists(profile_path):
                os.remove(profile_path)

    @patch("engines.config.get_setting")
    @patch("engines.app_commands.get_setting")
    def test_branch_session_preserves_score(
        self, mock_cmd_get_setting, mock_cfg_get_setting
    ):
        profile = {"name": "TestAI", "relationship_score": 77}
        os.makedirs("profiles", exist_ok=True)
        profile_path = "profiles/TestAI.json"
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=4)

        try:
            # 1. Mock get_setting for both modules first so save_history gets serializable values
            def debug_get_setting(key, default=None):
                return {
                    "current_character_profile": "TestAI.json",
                    "session_TestAI": "source_sess",
                }.get(key, default)

            mock_cmd_get_setting.side_effect = debug_get_setting
            mock_cfg_get_setting.side_effect = debug_get_setting

            # 2. Save history with score 42 in "source_sess"
            self.manager.save_history(
                "TestAI",
                [{"role": "user", "content": "Hello"}],
                relationship_score=42,
                session_name="source_sess",
            )

            # 3. Run branching command: //session branch dest_sess
            from engines.app_commands import SessionChangedRequested

            with self.assertRaises(SessionChangedRequested):
                app_commands("//session branch dest_sess", suppress_output=True)

            # 4. Verify branched session has the score 42
            data = self.manager.get_full_data("TestAI", session_name="dest_sess")
            self.assertEqual(data["metadata"]["relationship_score"], 42)

        finally:
            if os.path.exists(profile_path):
                os.remove(profile_path)

    @patch("engines.responses.get_sentiment_score")
    @patch("engines.responses.get_pipeline_flags")
    @patch("engines.responses.build_system_prompt")
    @patch("engines.responses.get_setting")
    @patch("engines.responses.ollama.chat")
    def test_relationship_score_damping_math(
        self,
        mock_ollama_chat,
        mock_get_setting,
        mock_build_system_prompt,
        mock_pipeline_flags,
        mock_get_sentiment
    ):
        profile = {"name": "TestAI", "llm_model": "test-model"}
        mock_get_setting.return_value = None
        mock_pipeline_flags.return_value = {"enabled": False}
        mock_ollama_chat.return_value = [{"message": {"content": "dummy"}}]

        # Case 1: positive change, positive score (damped)
        # Score = 50.0, raw change = +5.0
        # Expected actual_change = 5.0 * (100 - 50)/100 = 2.50
        # Expected new score = 52.50
        self.manager.save_history("TestAI", [], relationship_score=50.0)
        mock_get_sentiment.return_value = 5
        list(get_respond_stream("hi", profile, history_profile_name="TestAI"))
        self.assertEqual(self.manager.get_full_data("TestAI")["metadata"]["relationship_score"], 52.5)

        # Case 2: positive change, negative score (linear recovery)
        # Score = -50.0, raw change = +5.0
        # Expected new score = -45.0
        self.manager.save_history("TestAI", [], relationship_score=-50.0)
        mock_get_sentiment.return_value = 5
        list(get_respond_stream("hi", profile, history_profile_name="TestAI"))
        self.assertEqual(self.manager.get_full_data("TestAI")["metadata"]["relationship_score"], -45.0)

        # Case 3: negative change, negative score (damped)
        # Score = -50.0, raw change = -5.0
        # Expected actual_change = -5.0 * (100 - 50)/100 = -2.50
        # Expected new score = -52.50
        self.manager.save_history("TestAI", [], relationship_score=-50.0)
        mock_get_sentiment.return_value = -5
        list(get_respond_stream("hi", profile, history_profile_name="TestAI"))
        self.assertEqual(self.manager.get_full_data("TestAI")["metadata"]["relationship_score"], -52.5)

        # Case 4: negative change, positive score (linear decay)
        # Score = 50.0, raw change = -5.0
        # Expected new score = 45.0
        self.manager.save_history("TestAI", [], relationship_score=50.0)
        mock_get_sentiment.return_value = -5
        list(get_respond_stream("hi", profile, history_profile_name="TestAI"))
        self.assertEqual(self.manager.get_full_data("TestAI")["metadata"]["relationship_score"], 45.0)

        # Case 5: positive change close to cap (guaranteed minimum change of 0.01)
        # Score = 99.9, raw change = +5.0
        # Expected actual_change = 5 * (100 - 99.9)/100 = 0.005 -> clamped to 0.01
        # Expected new score = 99.9 + 0.01 = 99.91
        self.manager.save_history("TestAI", [], relationship_score=99.9)
        mock_get_sentiment.return_value = 5
        list(get_respond_stream("hi", profile, history_profile_name="TestAI"))
        self.assertEqual(self.manager.get_full_data("TestAI")["metadata"]["relationship_score"], 99.91)

    @patch("engines.responses.ollama.chat")
    @patch("engines.responses.get_setting")
    def test_get_sentiment_score_passes_recent_history_context(self, mock_get_setting, mock_ollama_chat):
        from engines.responses import get_sentiment_score
        mock_get_setting.return_value = "llama3.2"
        mock_ollama_chat.return_value = {"message": {"content": '{"rel": 3}'}}

        recent_history = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "How can I help you?"},
            {"role": "user", "content": "Do you like cookies?"}
        ]

        profile = {"name": "TestAI"}
        score = get_sentiment_score("Yes, I love them!", model="llama3.2", profile=profile, recent_history=recent_history)
        
        self.assertEqual(score, 3)
        # Verify the messages list passed to ollama.chat contains the history context
        called_messages = mock_ollama_chat.call_args[1]["messages"]
        self.assertEqual(len(called_messages), 5) # 1 system, 3 history, 1 user_input
        self.assertEqual(called_messages[1]["content"], "Hello!")
        self.assertEqual(called_messages[2]["content"], "How can I help you?")
        self.assertEqual(called_messages[3]["content"], "Do you like cookies?")
        self.assertIn("[USER_MSG]\nYes, I love them!", called_messages[4]["content"])


if __name__ == "__main__":
    unittest.main()
