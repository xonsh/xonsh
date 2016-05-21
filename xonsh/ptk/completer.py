# -*- coding: utf-8 -*-
"""Completer implementation to use with prompt_toolkit."""
import os
import builtins

from prompt_toolkit.layout.dimension import LayoutDimension
from prompt_toolkit.completion import Completer, Completion

from xonsh.platform import ptk_version


class PromptToolkitCompleter(Completer):
    """Simple prompt_toolkit Completer object.

    It just redirects requests to normal Xonsh completer.
    """

    def __init__(self, completer, ctx):
        """Takes instance of xonsh.completer.Completer and dict with context."""
        self.completer = completer
        self.ctx = ctx

    def get_completions(self, document, complete_event):
        """Returns a generator for list of completions."""

        #  Only generate completions when the user hits tab.
        if complete_event.completion_requested:
            line = document.current_line.lstrip()
            endidx = document.cursor_position_col
            begidx = line[:endidx].rfind(' ') + 1 if line[:endidx].rfind(' ') >= 0 else 0
            prefix = line[begidx:endidx]
            completions, l = self.completer.complete(prefix,
                                                     line,
                                                     begidx,
                                                     endidx,
                                                     self.ctx)
            if len(completions) <= 1:
                pass
            elif len(os.path.commonprefix(completions)) <= len(prefix):
                self.reserve_space()
            for comp in completions:
                yield Completion(comp, -l)

    def reserve_space(self):
        cli = builtins.__xonsh_shell__.shell.prompter.cli
        if ptk_version().startswith("1.0"):
            # This is the layout for ptk 1.0
            window = cli.application.layout.children[0].content.children[1]
        else:
            #TODO remove after next prompt_toolkit release
            try:
                #old layout to be removed at next ptk release
                window = cli.application.layout.children[1].children[1].content
            except AttributeError:
                #new layout to become default
                window = cli.application.layout.children[1].content

        if window and window.render_info:
            h = window.render_info.content_height
            r = builtins.__xonsh_env__.get('COMPLETIONS_MENU_ROWS')
            size = h + r
            def comp_height(cli):
                # If there is an autocompletion menu to be shown, make sure that o
                # layout has at least a minimal height in order to display it.
                if not cli.is_done:
                    return LayoutDimension(min=size)
                else:
                    return LayoutDimension()
            window._height = comp_height
