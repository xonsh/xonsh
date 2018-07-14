"""A prompt-toolkit v2 inspired shortcut collection."""
import builtins
import textwrap

from prompt_toolkit.enums import EditingMode
from prompt_toolkit.utils import DummyContext

from xonsh.platform import ptk_version_info
import xonsh.tools as xt

from prompt_toolkit.shortcuts.prompt import PromptSession


class Prompter:
    """Prompter for ptk 2.0
    """
    def __init__(self, app=None, *args, **kwargs):
        """Implements a prompt that statefully holds a command-line
        interface.  When used as a context manager, it will return itself
        on entry and reset itself on exit.

        Parameters
        ----------
        cli : CommandLineInterface or None, optional
            If this is not a CommandLineInterface object, such an object
            will be created when the prompt() method is called.
        """
        # TODO: maybe call this ``.prompt`` now since
        # ``CommandLineInterface`` is gone?
        self.app = app or PromptSession(**kwargs)
        self.major_minor = ptk_version_info()[:2]

    def __enter__(self):
        self.reset()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def prompt(self, message='', **kwargs):
        """Get input from the user and return it.
        """
        if builtins.__xonsh_env__.get('VI_MODE'):
            editing_mode = EditingMode.VI
        else:
            editing_mode = EditingMode.EMACS

        kwargs['editing_mode'] = editing_mode

        # A bottom toolbar is displayed if some FormattedText has been passed.
        # However, if this is an empty list, we don't want to show a toolbar.
        # (Better would be to pass `None`.)
        if kwargs['bottom_toolbar'] and kwargs['bottom_toolbar'].__pt_formatted_text__() == []:
            kwargs['bottom_toolbar'] = None

        return self.app.prompt(message=message, **kwargs)

    def reset(self):
        """Resets the prompt and cli to a pristine state on this object."""
        # XXX Is this necessary any more?
        #self.prompt = None
        pass
