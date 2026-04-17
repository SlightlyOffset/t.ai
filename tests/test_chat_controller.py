import unittest
from unittest.mock import patch

from engines.app_commands import RegenerateRequested
from engines.chat_controller import (
    get_user_message_number,
    handle_command_input,
    next_response_variant_or_regen,
    previous_response_variant,
)


class TestChatController(unittest.TestCase):
    @patch("engines.chat_controller.memory_manager.get_history_length", return_value=4)
    def test_get_user_message_number_non_command(self, _mock_len):
        self.assertEqual(get_user_message_number("hello", "profile"), 5)
        self.assertIsNone(get_user_message_number("//help", "profile"))

    @patch("engines.chat_controller.memory_manager.load_history")
    @patch("engines.chat_controller.app_commands")
    def test_handle_command_input_success(self, mock_app_commands, mock_history):
        mock_app_commands.return_value = (True, ["ok"])
        mock_history.return_value = []
        result = handle_command_input("//help", "profile")
        self.assertEqual(result, {"type": "command_success", "messages": ["ok"]})

    @patch(
        "engines.chat_controller.memory_manager.load_history",
        return_value=[{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}],
    )
    @patch("engines.chat_controller.app_commands", side_effect=RegenerateRequested())
    def test_handle_command_input_regenerate(self, _mock_app_commands, _mock_history):
        result = handle_command_input("//regen", "profile")
        self.assertEqual(result["type"], "regenerate")
        self.assertEqual(result["user_text"], "x")

    @patch("engines.chat_controller.memory_manager.save_history")
    @patch("engines.chat_controller.memory_manager.load_history")
    def test_previous_and_next_variants(self, mock_load_history, mock_save_history):
        history = [
            {"role": "user", "content": "u"},
            {
                "role": "assistant",
                "content": "b",
                "alternatives": ["a", "b", "c"],
                "selected_index": 1,
            },
        ]
        mock_load_history.return_value = history

        prev = previous_response_variant("profile")
        self.assertEqual(prev["content"], "a")
        self.assertEqual(prev["index"], 0)

        history[-1]["selected_index"] = 1
        history[-1]["content"] = "b"
        nxt = next_response_variant_or_regen("profile")
        self.assertEqual(nxt["type"], "next")
        self.assertEqual(nxt["content"], "c")
        self.assertTrue(mock_save_history.called)


if __name__ == "__main__":
    unittest.main()
