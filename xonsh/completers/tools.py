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
