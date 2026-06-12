import unittest
from unittest.mock import patch
from engines.prompts import build_system_prompt

class TestPrompts(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "name": "Astgenne",
            "alt_names": "Elena Urbica",
            "personality_type": "INTJ - The Decisive Nerd",
            "backstory": "Born into a family of astrologers...",
            "rp_mannerisms": ["Uses a honeyed tone", "Blunt commentary"],
            "character_info": {
                "gender": "Female",
                "age": "20s",
                "appearance": "Slim, porcelain body...",
                "likes": ["Making coffee", "DIY machinery"],
                "dislikes": ["Pointless chicanery"],
                "other": "Has basic medical training."
            },
            "system_prompt": "You are Astgenne."
        }

    @patch("engines.prompts.load_user_profile")
    def test_build_system_prompt_rp_mode(self, mock_load_user):
        mock_load_user.return_value = {
            "name": "Manganese",
            "personality_type": "Curious",
            "character_info": {
                "appearance": "Tall",
                "pet": "None",
                "likes": ["Science"]
            },
            "rp_mannerisms": ["Attentive listener"]
        }

        prompt = build_system_prompt(self.profile, 50, mode="rp")
        
        # Verify all detail fields are present in RP mode
        self.assertIn("Backstory: Born into a family of astrologers...", prompt)
        self.assertIn("Likes: Making coffee, DIY machinery", prompt)
        self.assertIn("Dislikes: Pointless chicanery", prompt)
        self.assertIn("Mannerisms: Uses a honeyed tone, Blunt commentary", prompt)
        self.assertIn("Name: Manganese", prompt)
        self.assertIn("Mode: RP", prompt)

    @patch("engines.prompts.load_user_profile")
    def test_build_system_prompt_casual_mode(self, mock_load_user):
        mock_load_user.return_value = {
            "name": "Manganese",
            "personality_type": "Curious",
            "character_info": {
                "appearance": "Tall",
                "pet": "None",
                "likes": ["Science"]
            },
            "rp_mannerisms": ["Attentive listener"]
        }

        prompt = build_system_prompt(self.profile, 50, mode="casual")
        
        # Verify detailed companion and user fields are NOT present in casual mode
        self.assertNotIn("Backstory: Born into a family of astrologers...", prompt)
        self.assertNotIn("Likes: Making coffee", prompt)
        self.assertNotIn("Dislikes: Pointless chicanery", prompt)
        self.assertNotIn("Mannerisms: Uses a honeyed tone", prompt)
        
        # Verify user profile details are also excluded
        self.assertNotIn("Personality: Curious", prompt)
        self.assertNotIn("Appearance: Tall", prompt)
        self.assertNotIn("Pet: None", prompt)
        self.assertNotIn("Likes: Science", prompt)
        self.assertNotIn("Mannerisms to watch for: Attentive listener", prompt)
        
        # Verify names and base prompt are still present
        self.assertIn("You are Astgenne.", prompt)
        self.assertIn("Name: Astgenne", prompt)
        self.assertIn("Name: Manganese", prompt)
        self.assertIn("Mode: CASUAL", prompt)

if __name__ == "__main__":
    unittest.main()
