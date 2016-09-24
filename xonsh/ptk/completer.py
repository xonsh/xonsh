# -*- coding: utf-8 -*-
"""Completer implementation to use with prompt_toolkit."""
import os
import builtins

from prompt_toolkit.layout.dimension import LayoutDimension
from prompt_toolkit.completion import Completer, Completion


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
            if self.completer is None:
                yield from []
            else:
                line = document.current_line.lstrip()
                line_ex = builtins.aliases.expand_alias(line)

                endidx = document.cursor_position_col
                begidx = (line[:endidx].rfind(' ') + 1
                          if line[:endidx].rfind(' ') >= 0 else 0)
                prefix = line[begidx:endidx]
                expand_offset = len(line_ex) - len(line)

                completions, l = self.completer.complete(prefix,
                                                         line_ex,
                                                         begidx + expand_offset,
                                                         endidx + expand_offset,
                                                         self.ctx)
                if len(completions) <= 1:
                    pass
                elif len(os.path.commonprefix(completions)) <= len(prefix):
                    self.reserve_space()

                # Find common prefix (strip quoting)
                c_prefix = os.path.commonprefix([a.strip('\'"')
                                                for a in completions])
                # Find last split symbol, do not trim the last part
                while c_prefix:
                    if c_prefix[-1] in r'/\.:@,':
                        break
                    c_prefix = c_prefix[:-1]

                for comp in completions:
                    # do not display quote
                    disp = comp.strip('\'"')[len(c_prefix):]
                    yield Completion(comp, -l, display=disp)

    def reserve_space(self):
        cli = builtins.__xonsh_shell__.shell.prompter.cli
        window = cli.application.layout.children[0].content.children[1]

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
