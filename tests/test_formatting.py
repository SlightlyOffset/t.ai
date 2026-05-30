import unittest

from engines.formatting import format_roleplay_text, format_summary_text, get_tts_split_points, TextFormatter


class TestFormatting(unittest.TestCase):
    def test_format_summary_text(self):
        summary = "## Header\n**Bold**\n* item"
        result = format_summary_text(summary)
        self.assertIn("[bold yellow]Memory Core Summary[/bold yellow]", result)
        self.assertIn("[b][u]Header[/u][/b]", result)
        self.assertIn("[b]Bold[/b]", result)
        self.assertIn("• item", result)

    def test_format_summary_cleans_legacy_tags(self):
        summary = "[bold yellow] Memory Core Summary [/bold yellow]\n## Header\n* item"
        result = format_summary_text(summary)
        # Check that [bold yellow] Memory Core Summary [/bold yellow] is stripped and prepended exactly once
        self.assertEqual(result.count("Memory Core Summary"), 1)
        self.assertIn("[bold yellow]Memory Core Summary[/bold yellow]\n\n", result)
        self.assertIn("• item", result)

    def test_format_summary_cleans_stray_tags(self):
        summary = "## Header\n[bold]Some bold[/bold]\n* item [yellow]tag[/yellow]"
        result = format_summary_text(summary)
        # Brackets inside summary should be stripped/escaped, not parsed as tags except for supported markdown
        self.assertNotIn("[bold]", result)
        self.assertNotIn("[yellow]", result)
        self.assertIn("Some bold", result)
        self.assertIn("tag", result)

    def test_format_roleplay_text_replaces_placeholders_and_styles(self):
        text = '{{user}} says "Hello" to *{{char}}*'
        result = format_roleplay_text(
            text=text,
            role="assistant",
            user_name="Alex",
            character_name="Nova",
            user_speech_color="cyan",
            assistant_speech_color="magenta",
        )
        self.assertIn("Alex says", result)
        self.assertIn('[magenta]"Hello"[/magenta]', result)
        self.assertIn("[i][dim]Nova[/dim][/i]", result)

    def test_get_tts_split_points_handles_ellipsis(self):
        text = "Hi... Hello!\n*Action* Done."
        points = get_tts_split_points(text)
        self.assertIn(text.index("!") + 1, points)
        self.assertIn(text.index("\n") + 1, points)
        self.assertIn(text.index("*") + 1, points)

    def test_text_formatter_class_directly(self):
        formatter = TextFormatter(
            user_name="John",
            character_name="AI",
            user_speech_color="cyan",
            assistant_speech_color="red"
        )
        # Test format_rp
        rp_res = formatter.format_rp('{{user}} and {{char}} say "hello"', role="assistant")
        self.assertIn("John and AI", rp_res)
        self.assertIn('[red]"hello"[/red]', rp_res)
        
        # Test format_summary
        sum_res = formatter.format_summary("## title\n**bold**")
        self.assertIn("[b][u]title[/u][/b]", sum_res)
        self.assertIn("[b]bold[/b]", sum_res)
        
        # Test get_tts_split_points
        points = formatter.get_tts_split_points("Hi. Hello!")
        self.assertIn(3, points)


if __name__ == "__main__":
    unittest.main()
