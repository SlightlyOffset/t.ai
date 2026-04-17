import unittest
from unittest.mock import patch

from engines.recap_service import (
    generate_recap_summary,
    generate_updated_memory_core,
    rolling_summary_target_index,
    split_recap_history,
)


class TestRecapService(unittest.TestCase):
    def test_split_recap_history_full_mode(self):
        state = split_recap_history([{"role": "user", "content": "x"}], short_history_limit=15, recent_window=5)
        self.assertEqual(state["mode"], "full")
        self.assertEqual(len(state["messages"]), 1)

    def test_split_recap_history_summary_mode(self):
        history = [{"role": "user", "content": str(i)} for i in range(20)]
        state = split_recap_history(history, short_history_limit=15, recent_window=5)
        self.assertEqual(state["mode"], "summary")
        self.assertEqual(len(state["older_history"]), 15)
        self.assertEqual(len(state["recent_history"]), 5)
        self.assertEqual(state["recent_start_index"], 16)

    def test_rolling_summary_target_index(self):
        self.assertIsNone(rolling_summary_target_index(history_len=20, last_index=10, memory_limit=15))
        self.assertEqual(rolling_summary_target_index(history_len=40, last_index=10, memory_limit=15), 25)

    @patch("engines.recap_service.generate_summary", return_value="summary")
    @patch("engines.recap_service.get_setting")
    def test_generate_recap_summary(self, mock_get_setting, mock_generate_summary):
        mock_get_setting.side_effect = lambda key, default=None: {"summarizer_model": "m", "remote_llm_url": "u"}.get(key, default)
        result = generate_recap_summary([{"role": "user", "content": "x"}], "Alex", "Nova")
        self.assertEqual(result, "summary")
        mock_generate_summary.assert_called_once()

    @patch("engines.recap_service.update_rolling_summary", return_value="new-core")
    @patch("engines.recap_service.get_setting")
    def test_generate_updated_memory_core(self, mock_get_setting, mock_update):
        mock_get_setting.side_effect = lambda key, default=None: {"summarizer_model": "m", "remote_llm_url": "u"}.get(key, default)
        result = generate_updated_memory_core("old", [{"role": "user", "content": "x"}], "Alex", "Nova")
        self.assertEqual(result, "new-core")
        mock_update.assert_called_once()


if __name__ == "__main__":
    unittest.main()
