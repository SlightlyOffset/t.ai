import unittest
from unittest.mock import MagicMock, patch

from engines.responses import _call_llm_once, get_respond_stream


class TestResponsesPipeline(unittest.TestCase):
    def setUp(self):
        # Force all background threads to run synchronously during tests to prevent race conditions
        self.thread_patcher = patch("threading.Thread.start", autospec=True)
        self.mock_thread_start = self.thread_patcher.start()
        
        def run_sync(mock_self):
            if mock_self._target:
                mock_self._target(*mock_self._args, **mock_self._kwargs)
                
        self.mock_thread_start.side_effect = run_sync
        
        # Clear the model tool support cache to ensure test independence
        import engines.responses
        if hasattr(engines.responses, "_MODEL_TOOL_SUPPORT_CACHE"):
            engines.responses._MODEL_TOOL_SUPPORT_CACHE.clear()

    def tearDown(self):
        self.thread_patcher.stop()

    @patch("engines.responses.get_setting")
    @patch("engines.responses.requests.post")
    def test_call_llm_once_remote_sends_repetition_penalty(self, mock_post, mock_get_setting):
        def side_effect(key, default=None):
            if key == "repetition_penalty":
                return 1.25
            if key == "privacy_mode":
                return False
            return default
        mock_get_setting.side_effect = side_effect
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "JSON remote reply"}}]
        }
        mock_response.text = ""
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        _call_llm_once(
            messages=[{"role": "user", "content": "Hi"}],
            model="test-model",
            remote_url="https://bridge.example",
            temperature=0.7,
            max_tokens=512,
        )

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["repetition_penalty"], 1.25)
        self.assertEqual(payload["temperature"], 0.7)
        self.assertEqual(payload["max_tokens"], 512)

    @patch("engines.responses.get_setting", return_value=1.3)
    @patch("engines.responses.ollama.chat")
    def test_call_llm_once_local_sends_repeat_penalty(self, mock_ollama_chat, _mock_get_setting):
        mock_ollama_chat.return_value = {"message": {"content": "Local reply"}}

        _call_llm_once(
            messages=[{"role": "user", "content": "Hi"}],
            model="test-model",
            remote_url=None,
            temperature=0.6,
            max_tokens=300,
        )

        options = mock_ollama_chat.call_args.kwargs["options"]
        self.assertEqual(options["repeat_penalty"], 1.3)
        self.assertEqual(options["temperature"], 0.6)

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
            "repetition_penalty": 1.4,
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
        # Find the POST call destined for the remote URL /chat
        remote_call = None
        for call in mock_post.call_args_list:
            if call.kwargs.get("json") and "messages" in call.kwargs["json"]:
                remote_call = call
                break
        self.assertIsNotNone(remote_call, "Remote LLM POST request was not found")
        payload = remote_call.kwargs["json"]
        self.assertEqual(payload["repetition_penalty"], 1.4)

    @patch("engines.responses.get_sentiment_score", return_value=0)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM")
    @patch("engines.responses.scan_for_lore", return_value="")
    @patch("engines.responses.load_lorebook", return_value={})
    @patch("engines.responses.ollama.chat", return_value=[])
    @patch("engines.responses.get_pipeline_flags")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.get_setting")
    def test_dynamic_truncation_no_starter(
        self,
        mock_get_setting,
        mock_memory_manager,
        mock_get_pipeline_flags,
        mock_ollama_chat,
        _mock_lorebook,
        _mock_scan,
        _mock_build_prompt,
        _mock_sentiment,
    ):
        profile = {"name": "TestAI", "llm_model": "test-model"}
        
        # History has 5 turns, each 6000 characters (~1500 tokens). Total ~7500 tokens > 6200 limit.
        history = [
            {"role": "user", "content": "A" * 6000},  # Index 0 (Oldest)
            {"role": "assistant", "content": "B" * 6000}, # Index 1
            {"role": "user", "content": "C" * 6000}, # Index 2
            {"role": "assistant", "content": "D" * 6000}, # Index 3
            {"role": "user", "content": "E" * 6000}, # Index 4 (Latest)
        ]
        full_data = {"metadata": {"current_scene": "Room", "memory_core": "", "narrative_state": {}}}

        mock_get_setting.side_effect = lambda key, default=None: {
            "default_llm_model": "test-model",
            "remote_llm_url": None,
            "interaction_mode": "rp",
            "memory_limit": 15,
        }.get(key, default)
        
        # Disable candidates & critic to run single pass _call_llm_once path
        mock_get_pipeline_flags.return_value = {
            "enabled": True,
            "instrumentation": False,
            "state": False,
            "memory": False,
            "planner": False,
            "candidates": False,
            "critic": False,
            "candidate_count": 1,
            "style_profile": "balanced",
        }
        mock_memory_manager.get_full_data.return_value = full_data
        mock_memory_manager.load_history.side_effect = [history, list(history)]

        # Run stream
        list(get_respond_stream("User prompt", profile, history_profile_name="test_profile"))
        
        # Verify that we popped from the front (index 0) because there's no assistant starter
        # Since each msg is 1500 tokens, 1500 * 5 = 7500. Truncation must pop until <= 6200.
        # Popping 0 (A) leaves: B (1500), C (1500), D (1500), E (1500) -> 6000 tokens.
        # So it should pop exactly 1 turn, leaving B, C, D, E.
        self.assertTrue(mock_ollama_chat.called)
        sent_messages = mock_ollama_chat.call_args_list[0].kwargs["messages"]
        
        # Extract the content of the history turns sent to the LLM (skipping system prompt and user input)
        history_contents = [m["content"] for m in sent_messages if m["role"] != "system" and m["content"] != "User prompt"]
        
        self.assertNotIn("A" * 6000, history_contents)
        self.assertIn("B" * 6000, history_contents)
        self.assertIn("E" * 6000, history_contents)

    @patch("engines.responses.get_sentiment_score", return_value=0)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM")
    @patch("engines.responses.scan_for_lore", return_value="")
    @patch("engines.responses.load_lorebook", return_value={})
    @patch("engines.responses.ollama.chat", return_value=[])
    @patch("engines.responses.get_pipeline_flags")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.get_setting")
    def test_dynamic_truncation_with_starter(
        self,
        mock_get_setting,
        mock_memory_manager,
        mock_get_pipeline_flags,
        mock_ollama_chat,
        _mock_lorebook,
        _mock_scan,
        _mock_build_prompt,
        _mock_sentiment,
    ):
        profile = {"name": "TestAI", "llm_model": "test-model"}
        
        # First message is assistant (starter message).
        history = [
            {"role": "assistant", "content": "STARTER" * 500}, # Index 0 (Starter) -> 3500 chars (~875 tokens)
            {"role": "user", "content": "A" * 6000},          # Index 1 -> 1500 tokens
            {"role": "assistant", "content": "B" * 6000},     # Index 2 -> 1500 tokens
            {"role": "user", "content": "C" * 6000},          # Index 3 -> 1500 tokens (Latest)
        ]
        # Total tokens = 875 + 1500 + 1500 + 1500 = 5375.
        # If we have system content and user_input, say system content is "SYSTEM" (1 token), user_input is 4000 chars (1000 tokens).
        # Total is 5375 + 1 + 1000 = 6376 > 6200 limit.
        # It must truncate. Since it has a starter, it should pop from index 1 ("A"), preserving "STARTER" (index 0).
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
            "state": False,
            "memory": False,
            "planner": False,
            "candidates": False,
            "critic": False,
            "candidate_count": 1,
            "style_profile": "balanced",
        }
        mock_memory_manager.get_full_data.return_value = full_data
        mock_memory_manager.load_history.side_effect = [history, list(history)]

        # Run stream with a large user_input (4000 chars -> 1000 tokens)
        user_input = "User prompt" * 400
        list(get_respond_stream(user_input, profile, history_profile_name="test_profile"))
        
        self.assertTrue(mock_ollama_chat.called)
        sent_messages = mock_ollama_chat.call_args_list[0].kwargs["messages"]
        
        # Extract the content of the history turns sent to the LLM (skipping system prompt and user input)
        history_contents = [m["content"] for m in sent_messages if m["role"] != "system" and m["content"] != user_input]
        
        # Verify starter is preserved
        self.assertIn("STARTER" * 500, history_contents)
        # Verify "A" (index 1) was popped first to keep starter
        self.assertNotIn("A" * 6000, history_contents)
        self.assertIn("B" * 6000, history_contents)
        self.assertIn("C" * 6000, history_contents)

    @patch("engines.responses.get_sentiment_score", return_value=0)
    @patch("engines.responses.build_system_prompt", return_value="SYSTEM_PROMPT")
    @patch("engines.responses.load_lorebook", return_value={})
    @patch("engines.responses.get_pipeline_flags")
    @patch("engines.responses.memory_manager")
    @patch("engines.responses.get_setting")
    @patch("engines.responses.ollama.chat")
    def test_get_respond_stream_parses_ollama_object_chunks(
        self,
        mock_ollama_chat,
        mock_get_setting,
        mock_memory_manager,
        mock_get_pipeline_flags,
        _mock_lorebook,
        _mock_build_system_prompt,
        _mock_sentiment,
    ):
        class MockMessage:
            def __init__(self, content):
                self.content = content

        class MockChatResponse:
            def __init__(self, content):
                self.message = MockMessage(content)

        profile = {"name": "TestAI", "llm_model": "test-model"}
        history = []
        full_data = {"metadata": {"current_scene": "Room", "memory_core": ""}}

        mock_get_setting.side_effect = lambda key, default=None: {
            "default_llm_model": "test-model",
            "remote_llm_url": None,
            "interaction_mode": "rp",
            "memory_limit": 15,
        }.get(key, default)

        mock_get_pipeline_flags.return_value = {
            "enabled": False,
        }
        mock_memory_manager.get_full_data.return_value = full_data
        mock_memory_manager.load_history.side_effect = [history, list(history)]

        # Mock the stream yielding ChatResponse objects (as in ollama v0.3.0+)
        mock_ollama_chat.return_value = [
            MockChatResponse("Hello "),
            MockChatResponse("world!"),
        ]

        result_chunks = list(get_respond_stream("Hi", profile, history_profile_name="test_profile"))
        self.assertEqual(result_chunks, ["Hello ", "world!"])

    @patch("engines.responses.requests.post")
    @patch("engines.responses.get_setting")
    def test_ollama_chat_compat_tool_calling_fallback(self, mock_get_setting, mock_post):
        # Setup configs
        def get_setting_mock(key, default=None):
            if key == "local_llm_url":
                return "http://127.0.0.1:11434/v1"
            if key == "debug_mode":
                return True
            return default
        mock_get_setting.side_effect = get_setting_mock
        
        # Test non-streaming error recovery (HTTP 400 with tools -> retries without tools)
        import requests
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 400
        mock_response_fail.raise_for_status.side_effect = requests.exceptions.HTTPError("Bad Request", response=mock_response_fail)
        
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Success content without tools"}}]
        }
        
        mock_post.side_effect = [mock_response_fail, mock_response_success]
        
        from engines.responses import _ollama_chat_compat
        
        result = _ollama_chat_compat(
            model="test-model",
            messages=[{"role": "user", "content": "test"}],
            stream=False,
            tools=[{"type": "function", "function": {"name": "test_tool"}}]
        )
        
        self.assertEqual(result["message"]["content"], "Success content without tools")
        self.assertEqual(mock_post.call_count, 2)
        # First call has tools
        self.assertIn("tools", mock_post.call_args_list[0].kwargs["json"])
        # Second call does not have tools
        self.assertNotIn("tools", mock_post.call_args_list[1].kwargs["json"])
        messages = mock_post.call_args_list[1].kwargs["json"]["messages"]
        self.assertEqual(messages[-1]["role"], "system")
        self.assertIn("tool-calling interface is unsupported", messages[-1]["content"])

    @patch("engines.responses.requests.post")
    @patch("engines.responses.get_setting")
    def test_ollama_chat_compat_stream_tool_calling_fallback(self, mock_get_setting, mock_post):
        def get_setting_mock(key, default=None):
            if key == "local_llm_url":
                return "http://127.0.0.1:11434/v1"
            if key == "debug_mode":
                return True
            return default
        mock_get_setting.side_effect = get_setting_mock
        
        # Test streaming error recovery
        import requests
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 400
        mock_response_fail.raise_for_status.side_effect = requests.exceptions.HTTPError("Bad Request", response=mock_response_fail)
        
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        # Mock generator/iterator for SSE stream
        mock_response_success.iter_lines.return_value = [
            'data: {"choices": [{"delta": {"content": "Stream chunk"}}]}'
        ]
        
        mock_post.side_effect = [mock_response_fail, mock_response_success]
        
        from engines.responses import _ollama_chat_compat
        
        generator = _ollama_chat_compat(
            model="test-model",
            messages=[{"role": "user", "content": "test"}],
            stream=True,
            tools=[{"type": "function", "function": {"name": "test_tool"}}]
        )
        
        chunks = list(generator)
        self.assertEqual(chunks[0]["message"]["content"], "Stream chunk")
        self.assertEqual(mock_post.call_count, 2)
        self.assertIn("tools", mock_post.call_args_list[0].kwargs["json"])
        self.assertNotIn("tools", mock_post.call_args_list[1].kwargs["json"])
        messages = mock_post.call_args_list[1].kwargs["json"]["messages"]
        self.assertEqual(messages[-1]["role"], "system")
        self.assertIn("tool-calling interface is unsupported", messages[-1]["content"])

    @patch("engines.responses.requests.post")
    @patch("engines.responses.get_setting")
    def test_ollama_chat_compat_tool_calling_caching(self, mock_get_setting, mock_post):
        # Setup configs
        def get_setting_mock(key, default=None):
            if key == "local_llm_url":
                return "http://127.0.0.1:11434/v1"
            return default
        mock_get_setting.side_effect = get_setting_mock
        
        import requests
        # First call fails with 400
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 400
        mock_response_fail.raise_for_status.side_effect = requests.exceptions.HTTPError("Bad Request", response=mock_response_fail)
        
        # Second call succeeds
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Success content 1"}}]
        }
        
        # Third call succeeds (subsequent call to the cached unsupported model)
        mock_response_success_2 = MagicMock()
        mock_response_success_2.status_code = 200
        mock_response_success_2.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "Success content 2"}}]
        }
        
        mock_post.side_effect = [mock_response_fail, mock_response_success, mock_response_success_2]
        
        from engines.responses import _ollama_chat_compat, _MODEL_TOOL_SUPPORT_CACHE
        
        # Call 1 (should fail -> fallback -> success)
        result1 = _ollama_chat_compat(
            model="cached-unsupported-model",
            messages=[{"role": "user", "content": "test"}],
            stream=False,
            tools=[{"type": "function", "function": {"name": "test_tool"}}]
        )
        self.assertEqual(result1["message"]["content"], "Success content 1")
        self.assertEqual(mock_post.call_count, 2)
        self.assertFalse(_MODEL_TOOL_SUPPORT_CACHE.get("cached-unsupported-model", True))
        
        # Call 2 (should be cached as unsupported, so it shouldn't send tools at all, hence only 1 call to requests.post)
        result2 = _ollama_chat_compat(
            model="cached-unsupported-model",
            messages=[{"role": "user", "content": "test"}],
            stream=False,
            tools=[{"type": "function", "function": {"name": "test_tool"}}]
        )
        self.assertEqual(result2["message"]["content"], "Success content 2")
        self.assertEqual(mock_post.call_count, 3) # 2 from before + 1 new call
        
        # Verify that tools was not in the payload of the last call
        last_call_json = mock_post.call_args_list[-1].kwargs["json"]
        self.assertNotIn("tools", last_call_json)
        self.assertEqual(last_call_json["messages"][-1]["role"], "system")
        self.assertIn("tool-calling interface is unsupported", last_call_json["messages"][-1]["content"])

    def test_tool_result_annotation_success(self):
        """Verify that successful tool results are prefixed with [TOOL RESULT - SUCCESS]."""
        import json
        # Plain text success
        result = "Successfully imported character card from cards/lyrei.png to profiles/Lyrei.json"
        _is_tool_error = False
        try:
            parsed = json.loads(result)
            _is_tool_error = "error" in parsed
        except (json.JSONDecodeError, TypeError):
            _is_tool_error = result.lower().startswith(("error", "failed"))

        self.assertFalse(_is_tool_error)
        annotated = f"[TOOL RESULT - {'ERROR' if _is_tool_error else 'SUCCESS'}]\n{result}"
        self.assertTrue(annotated.startswith("[TOOL RESULT - SUCCESS]"))
        self.assertIn(result, annotated)

    def test_tool_result_annotation_error_json(self):
        """Verify that JSON error tool results are prefixed with [TOOL RESULT - ERROR]."""
        import json
        result = json.dumps({"error": "Tool execution returned an error."})
        _is_tool_error = False
        try:
            parsed = json.loads(result)
            _is_tool_error = "error" in parsed
        except (json.JSONDecodeError, TypeError):
            _is_tool_error = result.lower().startswith(("error", "failed"))

        self.assertTrue(_is_tool_error)
        annotated = f"[TOOL RESULT - {'ERROR' if _is_tool_error else 'SUCCESS'}]\n{result}"
        self.assertTrue(annotated.startswith("[TOOL RESULT - ERROR]"))

    def test_tool_result_annotation_error_plaintext(self):
        """Verify that plain-text error/failed results are prefixed with [TOOL RESULT - ERROR]."""
        import json
        for result in ["Error importing card: some exception", "Failed to import character card from foo.png."]:
            _is_tool_error = False
            try:
                parsed = json.loads(result)
                _is_tool_error = "error" in parsed
            except (json.JSONDecodeError, TypeError):
                _is_tool_error = result.lower().startswith(("error", "failed"))

            self.assertTrue(_is_tool_error, f"Expected error detection for: {result}")
            annotated = f"[TOOL RESULT - {'ERROR' if _is_tool_error else 'SUCCESS'}]\n{result}"
            self.assertTrue(annotated.startswith("[TOOL RESULT - ERROR]"))


if __name__ == "__main__":
    unittest.main()
