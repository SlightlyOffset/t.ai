import unittest
from unittest.mock import patch, MagicMock
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

if __name__ == '__main__':
    unittest.main()
