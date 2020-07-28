"""Xonsh completer tools."""
import builtins
import textwrap


def _filter_normal(s, x):
    return s.startswith(x)


def _filter_ignorecase(s, x):
    return s.lower().startswith(x.lower())


def get_filter_function():
    """
    Return an appropriate filtering function for completions, given the valid
    of $CASE_SENSITIVE_COMPLETIONS
    """
    csc = builtins.__xonsh__.env.get("CASE_SENSITIVE_COMPLETIONS")
    if csc:
        return _filter_normal
    else:
        return _filter_ignorecase


def justify(s, max_length, left_pad=0):
    """
    Re-wrap the string s so that each line is no more than max_length
    characters long, padding all lines but the first on the left with the
    string left_pad.
    """
    txt = textwrap.wrap(s, width=max_length, subsequent_indent=" " * left_pad)
    return "\n".join(txt)


class RichCompletion(str):
    """A rich completion that completers can return instead of a string

    Parameters
    ----------
    value : str
        The completion's actual value.
    prefix_len : int
        Length of the prefix to be replaced in the completion.
        If None, the default prefix len will be used.
    display : str
        Text to display in completion option list.
        If None, ``value`` will be used.
    description : str
        Extra text to display when the completion is selected.
    """

    def __new__(cls, value, prefix_len=None, display=None, description=""):
        completion = super().__new__(cls, value)

        completion.prefix_len = prefix_len
        completion.display = display or value
        completion.description = description

        return completion

    def __repr__(self):
        return "RichCompletion({}, prefix_len={}, display={}, description={})".format(
            repr(str(self)),
            self.prefix_len,
            repr(self.display),
            repr(self.description),
        )


def get_ptk_completer():
    """Get the current PromptToolkitCompleter

    This is usefull for completers that want to use
    PromptToolkitCompleter.current_document (the current multiline document).

    Call this function lazily since in '.xonshrc' the shell doesn't exist.

    Returns
    -------
    The PromptToolkitCompleter if running with ptk, else returns None
    """
    if __xonsh__.shell is None or __xonsh__.shell.shell_type != "prompt_toolkit":
        return None

    return __xonsh__.shell.shell.pt_completer
