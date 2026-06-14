import unittest
from unittest.mock import patch
from engines.responses import generate_summary

class TestSummarizer(unittest.TestCase):
    def test_generate_summary_local(self):
        # Mock messages
        messages = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I am fine, thank you!"}
        ]
        
        # Mock ollama.chat
        mock_response = {'message': {'content': 'Summary of conversation'}}
        with patch('ollama.chat', return_value=mock_response) as mock_chat:
            summary = generate_summary(messages, model="phi3")
            
            self.assertEqual(summary, 'Summary of conversation')
            mock_chat.assert_called_once()
            # Check if messages in call contain our history
            call_args = mock_chat.call_args[1]
            self.assertIn("Hello, how are you?", call_args['messages'][1]['content'])

    def test_generate_summary_remote(self):
        # NOTE: Current implementation always uses local Ollama for summaries (Hybrid Offloading)
        # Mock messages
        messages = [
            {"role": "user", "content": "What is the weather like?"},
            {"role": "assistant", "content": "It is sunny today."}
        ]
        
        # Mock ollama.chat since the code currently ignores remote_url for summaries
        mock_response = {'message': {'content': 'Weather summary'}}
        with patch('ollama.chat', return_value=mock_response) as mock_chat:
            summary = generate_summary(messages, model="phi3", remote_url="http://remote-api")
            
            self.assertEqual(summary, 'Weather summary')
            mock_chat.assert_called_once()

    def test_update_rolling_summary(self):
        from engines.responses import update_rolling_summary
        
        existing_core = "The cat named Whiskers loves mice."
        new_messages = [
            {"role": "user", "content": "Whiskers caught a bird today."},
            {"role": "assistant", "content": "Oh, that's unusual for him!"}
        ]
        
        mock_response = {'message': {'content': 'Whiskers usually loves mice but caught a bird today.'}}
        with patch('ollama.chat', return_value=mock_response) as mock_chat:
            new_summary = update_rolling_summary(existing_core, new_messages, model="phi3")
            
            self.assertEqual(new_summary, 'Whiskers usually loves mice but caught a bird today.')
            mock_chat.assert_called_once()
            # Verify prompt contains both existing core and new messages
            call_args = mock_chat.call_args[1]
            self.assertIn(existing_core, call_args['messages'][1]['content'])
            self.assertIn("Whiskers caught a bird today.", call_args['messages'][1]['content'])

    def test_generate_summary_strips_tags_and_headers(self):
        messages = [{"role": "user", "content": "hello"}]
        mock_response = {
            'message': {
                'content': '[bold yellow] Memory Core Summary [/bold yellow]\nMemory Core Summary:\n- Conversed with user.\n[yellow]stray[/yellow]'
            }
        }
        with patch('ollama.chat', return_value=mock_response):
            summary = generate_summary(messages, model="phi3")
            # Should strip tags, headers, and colon
            self.assertEqual(summary, '- Conversed with user.\nstray')

    def test_update_rolling_summary_strips_tags_and_headers(self):
        from engines.responses import update_rolling_summary
        existing_core = "old"
        new_messages = [{"role": "user", "content": "new"}]
        mock_response = {
            'message': {
                'content': '[bold yellow] Memory Core Summary [/bold yellow]\n- updated info'
            }
        }
        with patch('ollama.chat', return_value=mock_response):
            new_summary = update_rolling_summary(existing_core, new_messages, model="phi3")
            self.assertEqual(new_summary, '- updated info')

    @patch("engines.responses.get_setting")
    def test_get_current_main_model_no_profile(self, mock_get_setting):
        from engines.responses import get_current_main_model
        
        # Test 1: No current character profile set
        mock_get_setting.side_effect = lambda key, default=None: {
            "current_character_profile": None,
            "default_llm_model": "fallback-llama"
        }.get(key, default)
        
        self.assertEqual(get_current_main_model(), "fallback-llama")

    @patch("engines.responses.os.path.exists", return_value=True)
    @patch("engines.responses.get_setting")
    def test_get_current_main_model_with_profile(self, mock_get_setting, mock_exists):
        from engines.responses import get_current_main_model
        import json
        
        mock_get_setting.side_effect = lambda key, default=None: {
            "current_character_profile": "TestChar.json",
            "default_llm_model": "fallback-llama"
        }.get(key, default)
        
        profile_content = json.dumps({"name": "Test", "llm_model": "custom-model"})
        with patch("builtins.open", unittest.mock.mock_open(read_data=profile_content)):
            self.assertEqual(get_current_main_model(), "custom-model")

    @patch("engines.responses.requests.post")
    @patch("engines.responses.get_setting")
    def test_unload_model_and_preload_main_basic(self, mock_get_setting, mock_post):
        from engines.responses import _unload_model_and_preload_main
        
        mock_get_setting.side_effect = lambda key, default=None: {
            "local_llm_url": "http://localhost:11434/v1",
            "remote_llm_url": None,
            "local_llm_keep_alive": 300
        }.get(key, default)
        
        # Unload gemma2:2b and preload llama3.2 (they are different)
        _unload_model_and_preload_main("gemma2:2b", "llama3.2")
        
        self.assertEqual(mock_post.call_count, 2)
        
        first_call_args = mock_post.call_args_list[0]
        self.assertEqual(first_call_args[0][0], "http://localhost:11434/api/generate")
        self.assertEqual(first_call_args[1]["json"], {"model": "gemma2:2b", "keep_alive": 0})
        
        second_call_args = mock_post.call_args_list[1]
        self.assertEqual(second_call_args[0][0], "http://localhost:11434/api/generate")
        self.assertEqual(second_call_args[1]["json"], {"model": "llama3.2", "keep_alive": 300})

    @patch("engines.responses.requests.post")
    @patch("engines.responses.get_setting")
    def test_unload_model_and_preload_main_same_model(self, mock_get_setting, mock_post):
        from engines.responses import _unload_model_and_preload_main
        
        mock_get_setting.side_effect = lambda key, default=None: {
            "local_llm_url": "http://localhost:11434/v1",
            "remote_llm_url": None
        }.get(key, default)
        
        # When unload_model == main_model and running locally, do nothing
        _unload_model_and_preload_main("llama3.2", "llama3.2")
        self.assertEqual(mock_post.call_count, 0)

    @patch("engines.responses.requests.post")
    @patch("engines.responses.requests.get")
    @patch("engines.responses.get_setting")
    def test_unload_all_models_success(self, mock_get_setting, mock_get, mock_post):
        from engines.responses import unload_all_models
        
        mock_get_setting.return_value = "http://localhost:11434/v1"
        
        # Mock get request to /api/ps returning running models
        mock_get_response = unittest.mock.Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "models": [
                {"model": "gemma2:2b", "name": "gemma2:2b"},
                {"model": "llama3:latest", "name": "llama3:latest"}
            ]
        }
        mock_get.return_value = mock_get_response
        
        # Mock post requests for /api/generate
        mock_post_response = unittest.mock.Mock()
        mock_post_response.status_code = 200
        mock_post.return_value = mock_post_response
        
        unload_all_models()
        
        # Verify /api/ps was called
        mock_get.assert_called_once_with("http://localhost:11434/api/ps", timeout=3)
        
        # Verify /api/generate was called for both models with keep_alive: 0
        self.assertEqual(mock_post.call_count, 2)
        call1 = mock_post.call_args_list[0]
        self.assertEqual(call1[0][0], "http://localhost:11434/api/generate")
        self.assertEqual(call1[1]["json"], {"model": "gemma2:2b", "keep_alive": 0})
        
        call2 = mock_post.call_args_list[1]
        self.assertEqual(call2[0][0], "http://localhost:11434/api/generate")
        self.assertEqual(call2[1]["json"], {"model": "llama3:latest", "keep_alive": 0})

if __name__ == '__main__':
    unittest.main()
