import unittest
import json
from unittest.mock import patch
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
        critic_json = {
            "persona_preservation_score": 9.0,
            "speech_style_alignment_score": 9.0,
            "accuracy_score": 9.0,
            "average_score": 9.0,
            "feedback": "Perfect profile."
        }
        mock_chat.side_effect = [
            {"message": {"content": json.dumps(refined_json)}},
            {"message": {"content": json.dumps(critic_json)}}
        ]

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

        # Check call arguments - should be called twice (generation and critique)
        self.assertEqual(mock_chat.call_count, 2)
        args, kwargs = mock_chat.call_args_list[0]
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

    def test_convert_to_project_format_raw_fields_and_examples(self):
        st_data = {
            "name": "Alice",
            "personality": "Very bubbly and happy",
            "description": "An adventurer from a distant land.",
            "scenario": "Meeting at a tavern",
            "mes_example": "Alice: *smiles warmly* Hello there!"
        }
        profile = CharacterImporter.convert_to_project_format(st_data)
        self.assertEqual(profile["raw_personality"], "Very bubbly and happy")
        self.assertEqual(profile["raw_description"], "An adventurer from a distant land.")
        self.assertEqual(profile["mes_example"], "Alice: *smiles warmly* Hello there!")

    @patch("ollama.chat")
    @patch("engines.config.get_setting", return_value="llama3.2")
    def test_run_critic_pass(self, mock_setting, mock_chat):
        mock_chat.return_value = {
            "message": {
                "content": json.dumps({
                    "persona_preservation_score": 9.5,
                    "speech_style_alignment_score": 9.0,
                    "accuracy_score": 8.5,
                    "average_score": 9.0,
                    "feedback": "Outstanding preservation of speech quirks."
                })
            }
        }
        profile = {"name": "Alice"}
        res = CharacterImporter.run_critic_pass(
            profile,
            raw_personality="bubbly",
            raw_description="adventurer",
            raw_scenario="tavern",
            raw_mes_example="Alice: *smiles*"
        )
        self.assertEqual(res["average_score"], 9.0)
        self.assertEqual(res["feedback"], "Outstanding preservation of speech quirks.")

    @patch("ollama.chat")
    @patch("engines.config.get_setting", return_value="llama3.2")
    def test_refine_character_profile_retry_loop(self, mock_setting, mock_chat):
        # First attempt (refinement): returns a profile
        # Second attempt (critic): returns a low score (e.g. 5.0)
        # Third attempt (correction): returns a corrected profile
        # Fourth attempt (critic): returns a high score (9.0)
        refined_json_1 = {"personality_type": "Somewhat bubbly"}
        critic_json_1 = {
            "persona_preservation_score": 5.0,
            "speech_style_alignment_score": 5.0,
            "accuracy_score": 5.0,
            "average_score": 5.0,
            "feedback": "Needs to be much more bubbly!"
        }
        refined_json_2 = {"personality_type": "Extremely bubbly and energetic!"}
        critic_json_2 = {
            "persona_preservation_score": 9.0,
            "speech_style_alignment_score": 9.0,
            "accuracy_score": 9.0,
            "average_score": 9.0,
            "feedback": "Perfect now."
        }

        mock_chat.side_effect = [
            {"message": {"content": json.dumps(refined_json_1)}},
            {"message": {"content": json.dumps(critic_json_1)}},
            {"message": {"content": json.dumps(refined_json_2)}},
            {"message": {"content": json.dumps(critic_json_2)}}
        ]

        base_profile = {
            "name": "Alice",
            "personality_type": "bubbly",
            "backstory": "adventurer",
            "character_info": {"other": "tavern"},
            "mes_example": "Alice: *giggles*"
        }

        refined = CharacterImporter.refine_character_profile(
            base_profile,
            interactive=False
        )

        self.assertEqual(refined["personality_type"], "Extremely bubbly and energetic!")
        self.assertEqual(mock_chat.call_count, 4)


    @patch("ollama.chat")
    @patch("engines.config.get_setting", return_value="llama3.2")
    def test_run_critic_pass_robust_parsing(self, mock_setting, mock_chat):
        # Mock responses using fractions ("9/10"), key name variations ("persona"), etc.
        mock_chat.return_value = {
            "message": {
                "content": json.dumps({
                    "persona": "9/10",
                    "speech": "8.5 out of 10",
                    "accuracy": 8,
                    "feedback": "Robust parsing works."
                })
            }
        }
        profile = {"name": "Alice"}
        res = CharacterImporter.run_critic_pass(
            profile,
            raw_personality="bubbly",
            raw_description="adventurer",
            raw_scenario="tavern",
            raw_mes_example="Alice: *smiles*"
        )
        self.assertEqual(res["persona_preservation_score"], 9.0)
        self.assertEqual(res["speech_style_alignment_score"], 8.5)
        self.assertEqual(res["accuracy_score"], 8.0)
        self.assertEqual(res["average_score"], 8.5)


if __name__ == "__main__":
    unittest.main()
