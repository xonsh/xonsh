"""The readline based xonsh shell.

Portions of this code related to initializing the readline library
are included from the IPython project.  The IPython project is:

* Copyright (c) 2008-2014, IPython Development Team
* Copyright (c) 2001-2007, Fernando Perez <fernando.perez@colorado.edu>
* Copyright (c) 2001, Janko Hauser <jhauser@zscout.de>
* Copyright (c) 2001, Nathaniel Gray <n8gray@caltech.edu>

"""
import cmd
import collections
import importlib
import os
import select
import shutil
import sys
import threading
import typing as tp

import xonsh.completers.tools as xct
from xonsh.ansi_colors import (
    ansi_color_style,
    ansi_color_style_names,
    ansi_partial_color_format,
)
from xonsh.base_shell import BaseShell
from xonsh.built_ins import XSH
from xonsh.events import events
from xonsh.lazyasd import LazyObject, lazyobject
from xonsh.lazyimps import pyghooks, pygments, winutils
from xonsh.platform import (
    ON_CYGWIN,
    ON_DARWIN,
    ON_MSYS,
    ON_POSIX,
    ON_WINDOWS,
    os_environ,
)
from xonsh.prompt.base import multiline_prompt
from xonsh.tools import (
    carriage_return,
    columnize,
    ends_with_colon_token,
    print_exception,
    to_bool,
)

if tp.TYPE_CHECKING:
    from types import ModuleType

readline: "ModuleType|None" = None
RL_COMPLETION_SUPPRESS_APPEND = RL_LIB = RL_STATE = None  # type: tp.Any
RL_COMPLETION_QUERY_ITEMS: "tp.Any" = None
RL_CAN_RESIZE = False
RL_VARIABLE_VALUE: "tp.Callable[..., tp.Any]|None" = None
_RL_STATE_DONE = 0x1000000
_RL_STATE_ISEARCH = 0x0000080

_RL_PREV_CASE_SENSITIVE_COMPLETIONS = "to-be-set"


def setup_readline():
    """Sets up the readline module and completion suppression, if available."""
    global RL_COMPLETION_SUPPRESS_APPEND, RL_LIB, RL_CAN_RESIZE, RL_STATE, readline, RL_COMPLETION_QUERY_ITEMS
    if RL_COMPLETION_SUPPRESS_APPEND is not None:
        return
    for _rlmod_name in ("gnureadline", "readline"):
        try:
            readline = importlib.import_module(_rlmod_name)
            sys.modules["readline"] = readline
        except ImportError:
            pass
        else:
            break

    if readline is None:
        print(
            """Skipping setup. Because no `readline` implementation available.
            Please install a backend (`readline`, `prompt-toolkit`, etc) to use
            `xonsh` interactively.
            See https://github.com/xonsh/xonsh/issues/1170"""
        )
        return

    import ctypes
    import ctypes.util

    uses_libedit = readline.__doc__ and "libedit" in readline.__doc__
    readline.set_completer_delims(" \t\n")
    # Cygwin seems to hang indefinitely when querying the readline lib
    if (not ON_CYGWIN) and (not ON_MSYS) and (not readline.__file__.endswith(".py")):
        RL_LIB = lib = ctypes.cdll.LoadLibrary(readline.__file__)
        try:
            RL_COMPLETION_SUPPRESS_APPEND = ctypes.c_int.in_dll(
                lib, "rl_completion_suppress_append"
            )
        except ValueError:
            # not all versions of readline have this symbol, ie Macs sometimes
            RL_COMPLETION_SUPPRESS_APPEND = None
        try:
            RL_COMPLETION_QUERY_ITEMS = ctypes.c_int.in_dll(
                lib, "rl_completion_query_items"
            )
        except ValueError:
            # not all versions of readline have this symbol, ie Macs sometimes
            RL_COMPLETION_QUERY_ITEMS = None
        try:
            RL_STATE = ctypes.c_int.in_dll(lib, "rl_readline_state")
        except Exception:
            pass
        RL_CAN_RESIZE = hasattr(lib, "rl_reset_screen_size")
    env = XSH.env
    # reads in history
    readline.set_history_length(-1)
    ReadlineHistoryAdder()
    # sets up IPython-like history matching with up and down
    readline.parse_and_bind('"\\e[B": history-search-forward')
    readline.parse_and_bind('"\\e[A": history-search-backward')
    # Setup Shift-Tab to indent
    readline.parse_and_bind('"\\e[Z": "{}"'.format(env.get("INDENT")))

    # handle tab completion differences found in libedit readline compatibility
    # as discussed at http://stackoverflow.com/a/7116997
    if uses_libedit and ON_DARWIN:
        readline.parse_and_bind("bind ^I rl_complete")
        print(
            "\n".join(
                [
                    "",
                    "*" * 78,
                    "libedit detected - readline will not be well behaved, including but not limited to:",
                    "   * crashes on tab completion",
                    "   * incorrect history navigation",
                    "   * corrupting long-lines",
                    "   * failure to wrap or indent lines properly",
                    "",
                    "It is highly recommended that you install gnureadline, which is installable with:",
                    "     xpip install gnureadline",
                    "*" * 78,
                ]
            ),
            file=sys.stderr,
        )
    else:
        readline.parse_and_bind("tab: complete")
    # try to load custom user settings
    inputrc_name = os_environ.get("INPUTRC")
    if inputrc_name is None:
        if uses_libedit:
            inputrc_name = ".editrc"
        else:
            inputrc_name = ".inputrc"
        inputrc_name = os.path.join(os.path.expanduser("~"), inputrc_name)
    if (not ON_WINDOWS) and (not os.path.isfile(inputrc_name)):
        inputrc_name = "/etc/inputrc"
    if ON_WINDOWS:
        winutils.enable_virtual_terminal_processing()
    if os.path.isfile(inputrc_name):
        try:
            readline.read_init_file(inputrc_name)
        except Exception:
            # this seems to fail with libedit
            print_exception("xonsh: could not load readline default init file.")

    # Protection against paste jacking (issue #1154)
    # This must be set after the init file is loaded since read_init_file()
    # automatically disables bracketed paste
    # (https://github.com/python/cpython/pull/24108)
    readline.parse_and_bind("set enable-bracketed-paste on")

    # properly reset input typed before the first prompt
    readline.set_startup_hook(carriage_return)


def teardown_readline():
    """Tears down up the readline module, if available."""
    try:
        import readline
    except (ImportError, TypeError):
        return


def _rebind_case_sensitive_completions():
    # handle case sensitive, see Github issue #1342 for details
    global _RL_PREV_CASE_SENSITIVE_COMPLETIONS
    env = XSH.env
    case_sensitive = env.get("CASE_SENSITIVE_COMPLETIONS")
    if case_sensitive is _RL_PREV_CASE_SENSITIVE_COMPLETIONS:
        return
    if case_sensitive:
        readline.parse_and_bind("set completion-ignore-case off")
    else:
        readline.parse_and_bind("set completion-ignore-case on")
    _RL_PREV_CASE_SENSITIVE_COMPLETIONS = case_sensitive


def fix_readline_state_after_ctrl_c():
    """
    Fix to allow Ctrl-C to exit reverse-i-search.

    Based on code from:
        http://bugs.python.org/file39467/raw_input__workaround_demo.py
    """
    if ON_WINDOWS:
        # hack to make pyreadline mimic the desired behavior
        try:
            _q = readline.rl.mode.process_keyevent_queue
            if len(_q) > 1:
                _q.pop()
        except Exception:
            pass
    if RL_STATE is None:
        return
    if RL_STATE.value & _RL_STATE_ISEARCH:
        RL_STATE.value &= ~_RL_STATE_ISEARCH
    if not RL_STATE.value & _RL_STATE_DONE:
        RL_STATE.value |= _RL_STATE_DONE


def rl_completion_suppress_append(val=1):
    """Sets the rl_completion_suppress_append variable, if possible.
    A value of 1 (default) means to suppress, a value of 0 means to enable.
    """
    if RL_COMPLETION_SUPPRESS_APPEND is None:
        return
    RL_COMPLETION_SUPPRESS_APPEND.value = val


def rl_completion_query_items(val=None):
    """Sets the rl_completion_query_items variable, if possible.
    A None value will set this to $COMPLETION_QUERY_LIMIT, otherwise any integer
    is accepted.
    """
    if RL_COMPLETION_QUERY_ITEMS is None:
        return
    if val is None:
        val = XSH.env.get("COMPLETION_QUERY_LIMIT")
    RL_COMPLETION_QUERY_ITEMS.value = val


def rl_variable_dumper(readable=True):
    """Dumps the currently set readline variables. If readable is True, then this
    output may be used in an inputrc file.
    """
    RL_LIB.rl_variable_dumper(int(readable))


def rl_variable_value(variable):
    """Returns the currently set value for a readline configuration variable."""
    global RL_VARIABLE_VALUE
    if RL_VARIABLE_VALUE is None:
        import ctypes

        RL_VARIABLE_VALUE = RL_LIB.rl_variable_value
        RL_VARIABLE_VALUE.restype = ctypes.c_char_p
    env = XSH.env
    enc, errors = env.get("XONSH_ENCODING"), env.get("XONSH_ENCODING_ERRORS")
    if isinstance(variable, str):
        variable = variable.encode(encoding=enc, errors=errors)
    rtn = RL_VARIABLE_VALUE(variable)
    return rtn.decode(encoding=enc, errors=errors)


@lazyobject
def rl_on_new_line():
    """Grabs one of a few possible redisplay functions in readline."""
    names = ["rl_on_new_line", "rl_forced_update_display", "rl_redisplay"]
    for name in names:
        func = getattr(RL_LIB, name, None)
        if func is not None:
            break
    else:

        def print_for_newline():
            print()

        func = print_for_newline
    return func


def _insert_text_func(s, readline):
    """Creates a function to insert text via readline."""

    def inserter():
        readline.insert_text(s)
        readline.redisplay()

    return inserter


def _render_completions(completions, prefix, prefix_len):
    """Render the completions according to the required prefix_len.

    Readline will replace the current prefix with the chosen rendered completion.
    """
    chopped = prefix[:-prefix_len] if prefix_len else prefix

    rendered_completions = []
    for comp in completions:
        if isinstance(comp, xct.RichCompletion) and comp.prefix_len is not None:
            if comp.prefix_len:
                comp = prefix[: -comp.prefix_len] + comp
            else:
                comp = prefix + comp
        elif chopped:
            comp = chopped + comp
        rendered_completions.append(comp)

    return rendered_completions


DEDENT_TOKENS = LazyObject(
    lambda: frozenset(["raise", "return", "pass", "break", "continue"]),
    globals(),
    "DEDENT_TOKENS",
)


class ReadlineShell(BaseShell, cmd.Cmd):
    """The readline based xonsh shell."""

    def __init__(self, completekey="tab", stdin=None, stdout=None, **kwargs):
        BaseShell.__init__(self, **kwargs)
        # super() doesn't pass the stdin/stdout to Cmd's init method correctly.
        # so calling it explicitly
        cmd.Cmd.__init__(self, completekey=completekey, stdin=stdin, stdout=stdout)

        setup_readline()
        self._current_indent = ""
        self._current_prompt = ""
        self._force_hide = None
        self._complete_only_last_table = {
            # Truth table for completions, keys are:
            # (prefix_begs_quote, prefix_ends_quote, i_ends_quote,
            #  last_starts_with_prefix, i_has_space)
            (True, True, True, True, True): True,
            (True, True, True, True, False): True,
            (True, True, True, False, True): False,
            (True, True, True, False, False): True,
            (True, True, False, True, True): False,
            (True, True, False, True, False): False,
            (True, True, False, False, True): False,
            (True, True, False, False, False): False,
            (True, False, True, True, True): True,
            (True, False, True, True, False): False,
            (True, False, True, False, True): False,
            (True, False, True, False, False): True,
            (True, False, False, True, True): False,
            (True, False, False, True, False): False,
            (True, False, False, False, True): False,
            (True, False, False, False, False): False,
            (False, True, True, True, True): True,
            (False, True, True, True, False): True,
            (False, True, True, False, True): True,
            (False, True, True, False, False): True,
            (False, True, False, True, True): False,
            (False, True, False, True, False): False,
            (False, True, False, False, True): False,
            (False, True, False, False, False): False,
            (False, False, True, True, True): False,
            (False, False, True, True, False): False,
            (False, False, True, False, True): False,
            (False, False, True, False, False): True,
            (False, False, False, True, True): True,
            (False, False, False, True, False): False,
            (False, False, False, False, True): False,
            (False, False, False, False, False): False,
        }
        self.cmdqueue = collections.deque()

    def __del__(self):
        teardown_readline()

    def singleline(self, store_in_history=True, **kwargs):
        """Reads a single line of input. The store_in_history kwarg
        flags whether the input should be stored in readline's in-memory
        history.
        """
        if not store_in_history:  # store current position to remove it later
            try:
                import readline
            except ImportError:
                store_in_history = True
            pos = readline.get_current_history_length() - 1
        events.on_pre_prompt_format.fire()
        prompt = self.prompt
        events.on_pre_prompt.fire()
        rtn = input(prompt)
        events.on_post_prompt.fire()
        if not store_in_history and pos >= 0:
            readline.remove_history_item(pos)
        return rtn

    def parseline(self, line):
        """Overridden to no-op."""
        return "", line, line

    def _querycompletions(self, completions, loc):
        """Returns whether or not we should show completions. 0 means that prefixes
        should not be shown, 1 means that there is a common prefix among all completions
        and they should be shown, while 2 means that there is no common prefix but
        we are under the query limit and they should be shown.
        """
        if os.path.commonprefix([c[loc:] for c in completions]):
            return 1
        elif len(completions) <= XSH.env.get("COMPLETION_QUERY_LIMIT"):
            return 2
        msg = f"\nDisplay all {len(completions)} possibilities? "
        msg += "({GREEN}y{RESET} or {RED}n{RESET})"
        self.print_color(msg, end="", flush=True, file=sys.stderr)
        yn = "x"
        while yn not in "yn":
            yn = sys.stdin.read(1)
        show_completions = to_bool(yn)
        print()
        if not show_completions:
            rl_on_new_line()
            return 0
        w, h = shutil.get_terminal_size()
        lines = columnize(completions, width=w)
        more_msg = self.format_color(
            "{YELLOW}==={RESET} more or "
            "{PURPLE}({RESET}q{PURPLE}){RESET}uit "
            "{YELLOW}==={RESET}"
        )
        while len(lines) > h - 1:
            print("".join(lines[: h - 1]), end="", flush=True, file=sys.stderr)
            lines = lines[h - 1 :]
            print(more_msg, end="", flush=True, file=sys.stderr)
            q = sys.stdin.read(1).lower()
            print(flush=True, file=sys.stderr)
            if q == "q":
                rl_on_new_line()
                return 0
        print("".join(lines), end="", flush=True, file=sys.stderr)
        rl_on_new_line()
        return 0

    def completedefault(self, prefix, line, begidx, endidx):
        """Implements tab-completion for text."""
        if self.completer is None:
            return []
        rl_completion_suppress_append()  # this needs to be called each time
        _rebind_case_sensitive_completions()
        rl_completion_query_items(val=999999999)
        prev_text = "".join(self.buffer)
        completions, plen = self.completer.complete(
            prefix,
            line,
            begidx,
            endidx,
            ctx=self.ctx,
            multiline_text=prev_text + line,
            cursor_index=len(prev_text) + endidx,
        )
        rtn_completions = _render_completions(completions, prefix, plen)

        rtn = []
        prefix_begs_quote = prefix.startswith("'") or prefix.startswith('"')
        prefix_ends_quote = prefix.endswith("'") or prefix.endswith('"')
        for i in rtn_completions:
            i_ends_quote = i.endswith("'") or i.endswith('"')
            last = i.rsplit(" ", 1)[-1]
            last_starts_prefix = last.startswith(prefix)
            i_has_space = " " in i
            key = (
                prefix_begs_quote,
                prefix_ends_quote,
                i_ends_quote,
                last_starts_prefix,
                i_has_space,
            )
            rtn.append(last if self._complete_only_last_table[key] else i)
        # return based on show completions
        show_completions = self._querycompletions(completions, endidx - begidx)
        if show_completions == 0:
            return []
        elif show_completions == 1:
            return rtn
        elif show_completions == 2:
            return completions
        else:
            raise ValueError("query completions flag not understood.")

    # tab complete on first index too
    completenames = completedefault  # type:ignore

    def _load_remaining_input_into_queue(self):
        buf = b""
        while True:
            r, w, x = select.select([self.stdin], [], [], 1e-6)
            if len(r) == 0:
                break
            buf += os.read(self.stdin.fileno(), 1024)
        if len(buf) > 0:
            buf = buf.decode().replace("\r\n", "\n").replace("\r", "\n")
            self.cmdqueue.extend(buf.splitlines(keepends=True))

    def postcmd(self, stop, line):
        """Called just before execution of line. For readline, this handles the
        automatic indentation of code blocks.
        """
        try:
            import readline
        except ImportError:
            return stop
        if self.need_more_lines:
            if len(line.strip()) == 0:
                readline.set_pre_input_hook(None)
                self._current_indent = ""
            elif ends_with_colon_token(line):
                ind = line[: len(line) - len(line.lstrip())]
                ind += XSH.env.get("INDENT")
                readline.set_pre_input_hook(_insert_text_func(ind, readline))
                self._current_indent = ind
            elif line.split(maxsplit=1)[0] in DEDENT_TOKENS:
                env = XSH.env
                ind = self._current_indent[: -len(env.get("INDENT"))]
                readline.set_pre_input_hook(_insert_text_func(ind, readline))
                self._current_indent = ind
            else:
                ind = line[: len(line) - len(line.lstrip())]
                if ind != self._current_indent:
                    insert_func = _insert_text_func(ind, readline)
                    readline.set_pre_input_hook(insert_func)
                    self._current_indent = ind
        else:
            readline.set_pre_input_hook(None)
        return stop

    def _cmdloop(self, intro=None):
        """Repeatedly issue a prompt, accept input, parse an initial prefix
        off the received input, and dispatch to action methods, passing them
        the remainder of the line as argument.

        This was forked from Lib/cmd.py from the Python standard library v3.4.3,
        (C) Python Software Foundation, 2015.
        """
        self.preloop()
        try:
            import readline

            if self.use_rawinput and self.completekey:
                self.old_completer = readline.get_completer()
                readline.set_completer(self.complete)
                readline.parse_and_bind(self.completekey + ": complete")
            have_readline = True
        except ImportError:
            have_readline = False
        try:
            if intro is not None:
                self.intro = intro
            if self.intro:
                self.stdout.write(str(self.intro) + "\n")
            stop = None
            while not stop:
                line = None
                exec_now = False
                if len(self.cmdqueue) > 0:
                    line = self.cmdqueue.popleft()
                    exec_now = line.endswith("\n")
                if self.use_rawinput and not exec_now:
                    inserter = (
                        None if line is None else _insert_text_func(line, readline)
                    )
                    if inserter is not None:
                        readline.set_pre_input_hook(inserter)
                    try:
                        line = self.singleline()
                    except EOFError:
                        if XSH.env.get("IGNOREEOF"):
                            self.stdout.write('Use "exit" to leave the shell.' "\n")
                            line = ""
                        else:
                            line = "EOF"
                    if inserter is not None:
                        readline.set_pre_input_hook(None)
                else:
                    self.print_color(self.prompt, file=self.stdout)
                    if line is not None:
                        os.write(self.stdin.fileno(), line.encode())
                    if not exec_now:
                        line = self.stdin.readline()
                    if len(line) == 0:
                        line = "EOF"
                    else:
                        line = line.rstrip("\r\n")
                    if have_readline and line != "EOF":
                        readline.add_history(line)
                if not ON_WINDOWS:
                    # select() is not fully functional on windows
                    self._load_remaining_input_into_queue()
                line = self.precmd(line)
                stop = self.onecmd(line)
                stop = self.postcmd(stop, line)
                if ON_WINDOWS:
                    winutils.enable_virtual_terminal_processing()
            self.postloop()
        finally:
            if self.use_rawinput and self.completekey:
                try:
                    import readline

                    readline.set_completer(self.old_completer)
                except ImportError:
                    pass

    def cmdloop(self, intro=None):
        while not XSH.exit:
            try:
                self._cmdloop(intro=intro)
            except (KeyboardInterrupt, SystemExit):
                print(file=self.stdout)  # Gives a newline
                fix_readline_state_after_ctrl_c()
                self.reset_buffer()
                intro = None

    @property
    def prompt(self):
        """Obtains the current prompt string."""
        global RL_LIB, RL_CAN_RESIZE
        if RL_CAN_RESIZE:
            # This is needed to support some system where line-wrapping doesn't
            # work. This is a bug in upstream Python, or possibly readline.
            RL_LIB.rl_reset_screen_size()
        if self.need_more_lines:
            if self.mlprompt is None:
                try:
                    self.mlprompt = multiline_prompt(curr=self._current_prompt)
                except Exception:  # pylint: disable=broad-except
                    print_exception()
                    self.mlprompt = "<multiline prompt error> "
            return self.mlprompt
        env = XSH.env  # pylint: disable=no-member
        p = env.get("PROMPT")
        # clear prompt level cache
        env["PROMPT_FIELDS"].reset()
        try:
            p = self.prompt_formatter(p)
        except Exception:  # pylint: disable=broad-except
            print_exception()
        hide = True if self._force_hide is None else self._force_hide
        p = ansi_partial_color_format(p, style=env.get("XONSH_COLOR_STYLE"), hide=hide)
        self._current_prompt = p
        self.settitle()
        return p

    def format_color(self, string, hide=False, force_string=False, **kwargs):
        """Readline implementation of color formatting. This uses ANSI color
        codes.
        """
        hide = hide if self._force_hide is None else self._force_hide
        style = XSH.env.get("XONSH_COLOR_STYLE")
        return ansi_partial_color_format(string, hide=hide, style=style)

    def print_color(self, string, hide=False, **kwargs):
        if isinstance(string, str):
            s = self.format_color(string, hide=hide)
        else:
            # assume this is a list of (Token, str) tuples and format it
            env = XSH.env
            style_overrides_env = env.get("XONSH_STYLE_OVERRIDES", {})
            self.styler.style_name = env.get("XONSH_COLOR_STYLE")
            self.styler.override(style_overrides_env)
            style_proxy = pyghooks.xonsh_style_proxy(self.styler)
            formatter = pyghooks.XonshTerminal256Formatter(style=style_proxy)
            s = pygments.format(string, formatter).rstrip()
        print(s, **kwargs)

    def color_style_names(self):
        """Returns an iterable of all available style names."""
        return ansi_color_style_names()

    def color_style(self):
        """Returns the current color map."""
        style = XSH.env.get("XONSH_COLOR_STYLE")
        return ansi_color_style(style=style)

    def restore_tty_sanity(self):
        """An interface for resetting the TTY stdin mode. This is highly
        dependent on the shell backend. Also it is mostly optional since
        it only affects ^Z backgrounding behaviour.
        """
        if not ON_POSIX:
            return
        stty, _ = XSH.commands_cache.lazyget("stty", (None, None))
        if stty is None:
            return
        # If available, we should just call the stty utility. This call should
        # not throw even if stty fails. It should also be noted that subprocess
        # calls, like the following, seem to be ineffective:
        #       subprocess.call([stty, 'sane'], shell=True)
        # My guess is that this is because Popen does some crazy redirecting
        # under the covers. This effectively hides the true TTY stdin handle
        # from stty. To get around this we have to use the lower level
        # os.system() function.
        os.system(stty + " sane")


class ReadlineHistoryAdder(threading.Thread):
    def __init__(self, wait_for_gc=True, *args, **kwargs):
        """Thread responsible for adding inputs from history to the
        current readline instance. May wait for the history garbage
        collector to finish.
        """
        super().__init__(*args, **kwargs)
        self.daemon = True
        self.wait_for_gc = wait_for_gc
        self.start()

    def run(self):
        try:
            import readline
        except ImportError:
            return
        hist = XSH.history
        if hist is None:
            return
        i = 1
        for h in hist.all_items():
            line = h["inp"].rstrip()
            if i == 1:
                pass
            elif line == readline.get_history_item(i - 1):
                continue
            readline.add_history(line)
            if RL_LIB is not None:
                RL_LIB.history_set_pos(i)
            i += 1
