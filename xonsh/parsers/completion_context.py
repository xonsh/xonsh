"""Implements the xonsh (tab-)completion context parser.
This parser is meant to parse a (possibly incomplete) command line.
"""
from typing import Optional


class CompletionContext:
    pass


class CompletionContextParser:
    """A parser to construct a completion context."""

    def parse(
        self, multiline_text: str, cursor_index: int
    ) -> Optional[CompletionContext]:
        """Returns a CompletionContext from a command line.

        Parameters
        ----------
        multiline_text : str
            The complete multiline text.
        cursor_index : int
            The current cursor's index in the multiline text.
        """
        return None
