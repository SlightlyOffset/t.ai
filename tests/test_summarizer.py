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
            summary = generate_summary(messages, model="bitnet")
            
            self.assertEqual(summary, 'Summary of conversation')
            mock_chat.assert_called_once()
            # Check if messages in call contain our history
            call_args = mock_chat.call_args[1]
            self.assertIn("Hello, how are you?", call_args['messages'][1]['content'])

    def test_generate_summary_remote(self):
        # Mock messages
        messages = [
            {"role": "user", "content": "What is the weather like?"},
            {"role": "assistant", "content": "It is sunny today."}
        ]
        
        # Mock requests.post
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Weather summary'}}]
        }
        with patch('requests.post', return_value=mock_response) as mock_post:
            summary = generate_summary(messages, model="bitnet", remote_url="http://remote-api")
            
            self.assertEqual(summary, 'Weather summary')
            mock_post.assert_called_once()

if __name__ == '__main__':
    unittest.main()
