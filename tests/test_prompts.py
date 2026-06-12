import unittest
from unittest.mock import patch
from engines.prompts import build_system_prompt

class TestPrompts(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "name": "Lily",
            "personality_type": "Curious and analytical",
            "backstory": "An AI assistant.",
            "rp_mannerisms": ["speaks with code snippets"],
            "character_info": {
                "age": "19",
                "appearance": "Silver hair",
                "likes": ["Coding"],
                "dislikes": ["Bugs"],
                "other": "Tavern scenario"
            },
            "system_prompt": "You are {{char}}."
        }

    @patch("engines.prompts.load_user_profile")
    def test_build_system_prompt_without_dialogue_examples(self, mock_load_user):
        mock_load_user.return_value = {
            "name": "User",
            "personality_type": "Friendly",
            "rp_mannerisms": [],
            "character_info": {}
        }

        prompt = build_system_prompt(self.profile, rel_score=0.0)
        self.assertIn("You are Lily.", prompt)
        self.assertNotIn("[DIALOGUE EXAMPLES]", prompt)

    @patch("engines.prompts.load_user_profile")
    def test_build_system_prompt_with_dialogue_examples(self, mock_load_user):
        mock_load_user.return_value = {
            "name": "User",
            "personality_type": "Friendly",
            "rp_mannerisms": [],
            "character_info": {}
        }

        profile_with_examples = self.profile.copy()
        profile_with_examples["mes_example"] = "Lily: *looks at code* Let's optimize it.\n{{user}}: Sure!"

        prompt = build_system_prompt(profile_with_examples, rel_score=0.0)
        self.assertIn("You are Lily.", prompt)
        self.assertIn("[DIALOGUE EXAMPLES]", prompt)
        self.assertIn("Lily: *looks at code* Let's optimize it.", prompt)
        # Verify placeholders in the dialogue examples were also replaced
        self.assertIn("User: Sure!", prompt)

if __name__ == "__main__":
    unittest.main()
