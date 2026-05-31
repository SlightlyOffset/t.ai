import re
from rich.markup import escape

def safe_escape(text: str) -> str:
    """Escape all square brackets and backslashes to prevent Rich markup parsing errors."""
    if not text:
        return ""
    return text.replace("\\", "\\\\").replace("[", "\\[")

class TextFormatter:
    """
    Centralized text formatting class.
    Handles formatting of chat messages (RP mode), session summaries, 
    and TTS splitting logic.
    """
    def __init__(
        self,
        user_name: str = "User",
        character_name: str = "Assistant",
        user_speech_color: str = "yellow",
        assistant_speech_color: str = "yellow",
    ):
        self.user_name = user_name
        self.character_name = character_name
        self.user_speech_color = user_speech_color
        self.assistant_speech_color = assistant_speech_color

    def format_rp(self, text: str, role: str) -> str:
        """Format roleplay text replacing placeholders and applying styles."""
        if not text:
            return ""

        text = text.replace("{{user}}", self.user_name).replace("{{char}}", self.character_name)
        text = text.replace("{{User}}", self.user_name).replace("{{Char}}", self.character_name)
        text = re.sub(r"\[SCENE:\s*.*?\]", "", text, flags=re.IGNORECASE).strip()
        
        # Escape brackets in the raw text so they are not parsed as invalid Rich markup tags
        text = safe_escape(text)

        text = re.sub(r"\*\*(.*?)\*\*", r"[b]\1[/b]", text, flags=re.DOTALL)
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"[i][dim]\1[/dim][/i]", text, flags=re.DOTALL)

        speech_color = self.assistant_speech_color if role == "assistant" else self.user_speech_color
        return re.sub(r'["“](.*?)["”]', fr'[{speech_color}]"\1"[/{speech_color}]', text, flags=re.DOTALL)

    @staticmethod
    def format_summary(summary: str) -> str:
        """Format summary markdown-like text into safe Rich markup."""
        if not summary:
            return ""

        # 1. Strip any legacy/hallucinated tags, headers, or bracket formatting
        cleaned = summary
        cleaned = re.sub(
            r"\[bold yellow\]\s*Memory Core Summary\s*\[/bold yellow\]",
            "",
            cleaned,
            flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r"\[/?(?:bold|yellow|b|u|i|dim|color|red|green|cyan|magenta|orange|blue|white|black|/color|/b|/u|/i|/dim)[^\]]*\]",
            "",
            cleaned,
            flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r"^(?:#+\s*)?Memory\s*Core\s*Summary\s*[:\-]*\s*$",
            "",
            cleaned,
            flags=re.MULTILINE | re.IGNORECASE
        )
        cleaned = cleaned.strip()

        # 2. Escape the clean text to prevent any LLM-hallucinated brackets from causing Rich markup errors
        text = safe_escape(cleaned)

        # 3. Apply safe formatting for markdown headers and bullet points
        text = re.sub(r"^##\s+(.*)$", r"[b][u]\1[/u][/b]", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*(.*?)\*\*", r"[b]\1[/b]", text, flags=re.DOTALL)
        text = text.replace("*", "•")

        # 4. Prepend the official correctly-formatted header
        header = "[bold yellow]Memory Core Summary[/bold yellow]\n\n"
        return header + text

    @staticmethod
    def get_tts_split_points(text: str) -> list[int]:
        """
        Find safe split points for TTS chunking.
        Splits on asterisk boundaries and sentence punctuation outside narration markers.
        """
        points: list[int] = []
        in_asterisks = False
        for index, char in enumerate(text):
            if char == "*":
                in_asterisks = not in_asterisks
                points.append(index + 1)
                continue

            if in_asterisks:
                continue

            if char in ".!?\n":
                if char == "." and index + 1 < len(text) and text[index + 1] == ".":
                    continue
                if char == "." and index > 0 and text[index - 1] == ".":
                    continue
                points.append(index + 1)
        return points

# Legacy function-based interfaces for backward compatibility and testing
def format_summary_text(summary: str) -> str:
    return TextFormatter.format_summary(summary)

def format_roleplay_text(
    text: str,
    role: str,
    user_name: str = "User",
    character_name: str = "Assistant",
    user_speech_color: str = "yellow",
    assistant_speech_color: str = "yellow",
) -> str:
    formatter = TextFormatter(
        user_name=user_name,
        character_name=character_name,
        user_speech_color=user_speech_color,
        assistant_speech_color=assistant_speech_color,
    )
    return formatter.format_rp(text, role)

def get_tts_split_points(text: str) -> list[int]:
    return TextFormatter.get_tts_split_points(text)
