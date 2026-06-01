import unittest
import json
from unittest.mock import patch, MagicMock
from engines.character_importer import CharacterImporter


class TestCharacterImporterRefine(unittest.TestCase):
    def setUp(self):
        self.base_profile = {
            "name": "Lily",
            "avatar_path": "img/No_Image_Error.png",
            "alt_names": "",
            "personality_type": "Analytical",
            "backstory": "An assistant.",
            "rp_mannerisms": [],
            "character_info": {
                "gender": "Unknown",
                "age": "Unknown",
                "appearance": "",
                "likes": [],
                "dislikes": [],
                "other": "Default scenario"
            }
        }
        self.raw_st_data = {
            "personality": "Very analytical and sharp",
            "description": "An assistant designed for coding.",
            "scenario": "Pair programming session",
            "mes_example": "Lily: *looks at the code* Let's optimize this."
        }

    @patch("ollama.chat")
    @patch("engines.config.get_setting", return_value="llama3.2")
    def test_refine_character_profile_success(self, mock_setting, mock_chat):
        # Set up a mock successful JSON response from ollama
        refined_json = {
            "alt_names": "Lily, Lilith",
            "gender": "Female",
            "age": "19",
            "appearance": "Silver hair, blue eyes",
            "likes": ["Coding", "Coffee"],
            "dislikes": ["Bugs"],
            "rp_mannerisms": ["speaks with code snippets"],
            "personality_type": "Curious and analytical",
            "backstory": "An AI assistant created to help write code.",
            "other": "Optimized programming scenario",
            "system_prompt": "You are Lily, a smart AI coder."
        }
        mock_chat.return_value = {
            "message": {
                "content": json.dumps(refined_json)
            }
        }

        refined = CharacterImporter.refine_character_profile(
            self.base_profile.copy(),
            raw_st_data=self.raw_st_data,
            model="llama3.2"
        )

        # Verify values were updated
        self.assertEqual(refined["alt_names"], "Lily, Lilith")
        self.assertEqual(refined["personality_type"], "Curious and analytical")
        self.assertEqual(refined["backstory"], "An AI assistant created to help write code.")
        self.assertEqual(refined["system_prompt"], "You are Lily, a smart AI coder.")
        self.assertEqual(refined["rp_mannerisms"], ["speaks with code snippets"])
        
        info = refined["character_info"]
        self.assertEqual(info["gender"], "Female")
        self.assertEqual(info["age"], "19")
        self.assertEqual(info["appearance"], "Silver hair, blue eyes")
        self.assertEqual(info["likes"], ["Coding", "Coffee"])
        self.assertEqual(info["dislikes"], ["Bugs"])
        self.assertEqual(info["other"], "Optimized programming scenario")

        # Check call arguments
        mock_chat.assert_called_once()
        args, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["model"], "llama3.2")
        self.assertEqual(kwargs["format"], "json")

    @patch("ollama.chat")
    @patch("engines.config.get_setting", return_value="llama3.2")
    def test_refine_character_profile_malformed_json_fallback(self, mock_setting, mock_chat):
        # Mock malformed JSON response
        mock_chat.return_value = {
            "message": {
                "content": "This is invalid JSON format: { 'alt_names': 'test' "
            }
        }

        profile_copy = self.base_profile.copy()
        refined = CharacterImporter.refine_character_profile(
            profile_copy,
            raw_st_data=self.raw_st_data
        )

        # The profile should be returned unmodified (fallback)
        self.assertEqual(refined, profile_copy)
        self.assertEqual(refined["alt_names"], "")
        self.assertEqual(refined["character_info"]["gender"], "Unknown")

    @patch("ollama.chat")
    @patch("engines.config.get_setting", return_value="llama3.2")
    def test_refine_character_profile_refusal_fallback(self, mock_setting, mock_chat):
        # Mock safety refusal response
        mock_chat.return_value = {
            "message": {
                "content": "I cannot fulfill this request because it violates safety guidelines."
            }
        }

        profile_copy = self.base_profile.copy()
        refined = CharacterImporter.refine_character_profile(
            profile_copy,
            raw_st_data=self.raw_st_data
        )

        # The profile should be returned unmodified
        self.assertEqual(refined, profile_copy)

    @patch("ollama.chat")
    @patch("engines.config.get_setting", return_value="llama3.2")
    def test_refine_character_profile_exception_fallback(self, mock_setting, mock_chat):
        # Mock connection error / exception
        mock_chat.side_effect = Exception("Ollama connection failed")

        profile_copy = self.base_profile.copy()
        refined = CharacterImporter.refine_character_profile(
            profile_copy,
            raw_st_data=self.raw_st_data
        )

        # Should handle exception and return original profile
        self.assertEqual(refined, profile_copy)


class TestCharacterImporterConvert(unittest.TestCase):
    def test_convert_to_project_format_listify_likes_dislikes(self):
        st_data = {
            "name": "Bob",
            "character_info": {
                "likes": "coffee, reading\ntea",
                "dislikes": ["bugs", "meetings"]
            },
            "llm_model": None,
            "voice_clone_ref": None
        }
        profile = CharacterImporter.convert_to_project_format(st_data)
        self.assertEqual(profile["name"], "Bob")
        self.assertEqual(profile["character_info"]["likes"], ["coffee", "reading", "tea"])
        self.assertEqual(profile["character_info"]["dislikes"], ["bugs", "meetings"])
        self.assertEqual(profile["llm_model"], "")
        self.assertEqual(profile["voice_clone_ref"], "")


if __name__ == "__main__":
    unittest.main()
