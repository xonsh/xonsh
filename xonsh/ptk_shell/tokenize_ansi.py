from prompt_toolkit import ANSI
from prompt_toolkit.formatted_text import to_formatted_text


def tokenize_ansi(tokens):
    """Checks a list of (token, str) tuples for ANSI escape sequences and
    extends the token list with the new formatted entries.
    During processing tokens are converted to ``prompt_toolkit.FormattedText``.
    Returns a list of similar (token, str) tuples.
    """
    formatted_tokens = to_formatted_text(tokens)
    ansi_tokens = []
    for style, text in formatted_tokens:
        if "\x1b" in text:
            formatted_ansi = to_formatted_text(ANSI(text))
            ansi_text = ""
            prev_style = ""
            for ansi_style, ansi_text_part in formatted_ansi:
                if prev_style == ansi_style:
                    ansi_text += ansi_text_part
                else:
                    ansi_tokens.append((prev_style or style, ansi_text))
                    prev_style = ansi_style
                    ansi_text = ansi_text_part
            ansi_tokens.append((prev_style or style, ansi_text))
        else:
            ansi_tokens.append((style, text))
    return ansi_tokens
