"""Implements a xonsh tracer."""

import importlib
import inspect
import linecache
import os
import re
import sys
import typing as tp

import xonsh.procs.pipelines as xpp
import xonsh.prompt.cwd as prompt
from xonsh.cli_utils import Annotated, Arg, ArgParserAlias
from xonsh.lib.inspectors import find_file
from xonsh.lib.lazyasd import LazyObject
from xonsh.lib.lazyimps import pyghooks, pygments
from xonsh.platform import HAS_PYGMENTS
from xonsh.tools import DefaultNotGiven, normabspath, print_color, to_bool

terminal = LazyObject(
    lambda: importlib.import_module("pygments.formatters.terminal"),
    globals(),
    "terminal",
)


class TracerType:
    """Represents a xonsh tracer object, which keeps track of all tracing
    state. This is a singleton.
    """

    _inst: tp.Optional["TracerType"] = None
    valid_events = frozenset(["line", "call"])

    def __new__(cls, *args, **kwargs):
        if cls._inst is None:
            cls._inst = super().__new__(cls, *args, **kwargs)
        return cls._inst

    def __init__(self):
        self.prev_tracer = DefaultNotGiven
        self.files = set()
        self.usecolor = True
        self.lexer = pyghooks.XonshLexer()
        self.formatter = terminal.TerminalFormatter()
        self._last = ("", -1)  # filename, lineno tuple

    def __del__(self):
        for f in set(self.files):
            self.stop(f)

    def color_output(self, usecolor):
        """Specify whether or not the tracer output should be colored."""
        # we have to use a function to set usecolor because of the way that
        # lazyasd works. Namely, it cannot dispatch setattr to the target
        # object without being unable to access its own __dict__. This makes
        # setting an attr look like getting a function.
        self.usecolor = usecolor

    def start(self, filename):
        """Starts tracing a file."""
        files = self.files
        if len(files) == 0:
            self.prev_tracer = sys.gettrace()
        files.add(normabspath(filename))
        sys.settrace(self.trace)
        curr = inspect.currentframe()
        for frame, fname, *_ in inspect.getouterframes(curr, context=0):
            if normabspath(fname) in files:
                frame.f_trace = self.trace

    def stop(self, filename):
        """Stops tracing a file."""
        filename = normabspath(filename)
        self.files.discard(filename)
        if len(self.files) == 0:
            sys.settrace(self.prev_tracer)
            curr = inspect.currentframe()
            for frame, fname, *_ in inspect.getouterframes(curr, context=0):
                if normabspath(fname) == filename:
                    frame.f_trace = self.prev_tracer
            self.prev_tracer = DefaultNotGiven

    def trace(self, frame, event, arg):
        """Implements a line tracing function."""
        if event not in self.valid_events:
            return self.trace
        fname = find_file(frame)
        if fname in self.files:
            lineno = frame.f_lineno
            curr = (fname, lineno)
            if curr != self._last:
                line = linecache.getline(fname, lineno).rstrip()
                s = tracer_format_line(
                    fname,
                    lineno,
                    line,
                    color=self.usecolor,
                    lexer=self.lexer,
                    formatter=self.formatter,
                )
                print_color(s)
                self._last = curr
        return self.trace

    def on_files(
        self,
        _args,
        files: Annotated[tp.Iterable[str], Arg(nargs="*")] = ("__file__",),
    ):
        """begins tracing selected files.

        Parameters
        ----------
        _args
            argv from alias parser
        files
            file paths to watch, use "__file__" (default) to select the current file.
        """

        for f in files:
            if f == "__file__":
                f = _find_caller(_args)
            if f is None:
                continue
            self.start(f)

    def off_files(
        self,
        _args,
        files: Annotated[tp.Iterable[str], Arg(nargs="*")] = ("__file__",),
    ):
        """removes selected files fom tracing.

        Parameters
        ----------
        files
            file paths to stop watching, use ``__file__`` (default) to select the current file.

        """
        for f in files:
            if f == "__file__":
                f = _find_caller(_args)
            if f is None:
                continue
            self.stop(f)

    def toggle_color(
        self,
        toggle: Annotated[bool, Arg(type=to_bool)] = False,
    ):
        """output color management for tracer

        Parameters
        ----------
        toggle
            true/false, y/n, etc. to toggle color usage.
        """
        self.color_output(toggle)


tracer = LazyObject(TracerType, globals(), "tracer")

COLORLESS_LINE = "{fname}:{lineno}:{line}"
COLOR_LINE = "{{PURPLE}}{fname}{{BLUE}}:" "{{GREEN}}{lineno}{{BLUE}}:" "{{RESET}}"


def tracer_format_line(fname, lineno, line, color=True, lexer=None, formatter=None):
    """Formats a trace line suitable for printing."""
    fname = min(fname, prompt._replace_home(fname), os.path.relpath(fname), key=len)
    if not color:
        return COLORLESS_LINE.format(fname=fname, lineno=lineno, line=line)
    cline = COLOR_LINE.format(fname=fname, lineno=lineno)
    if not HAS_PYGMENTS:
        return cline + line
    # OK, so we have pygments
    tokens = pyghooks.partial_color_tokenize(cline)
    lexer = lexer or pyghooks.XonshLexer()
    tokens += pygments.lex(line, lexer=lexer)
    if tokens[-1][1] == "\n":
        del tokens[-1]
    elif tokens[-1][1].endswith("\n"):
        tokens[-1] = (tokens[-1][0], tokens[-1][1].rstrip())
    return tokens


#
# Command line interface
#


def _find_caller(args):
    """Somewhat hacky method of finding the __file__ based on the line executed."""
    re_line = re.compile(r"[^;\s|&<>]+\s+" + r"\s+".join(args))
    curr = inspect.currentframe()
    for _, fname, lineno, _, lines, _ in inspect.getouterframes(curr, context=1)[3:]:
        if lines is not None and re_line.search(lines[0]) is not None:
            return fname
        elif (
            lineno == 1 and re_line.search(linecache.getline(fname, lineno)) is not None
        ):
            # There is a bug in CPython such that getouterframes(curr, context=1)
            # will actually return the 2nd line in the code_context field, even though
            # line number is itself correct. We manually fix that in this branch.
            return fname
    else:
        msg = (
            "xonsh: warning: __file__ name could not be found. You may be "
            "trying to trace interactively. Please pass in the file names "
            "you want to trace explicitly."
        )
        print(msg, file=sys.stderr)


class TracerAlias(ArgParserAlias):
    """Tool for tracing xonsh code as it runs."""

    def build(self):
        parser = self.create_parser(prog="trace", empty_help=True)
        parser.add_command(tracer.on_files, prog="on", aliases=["start", "add"])
        parser.add_command(tracer.off_files, prog="off", aliases=["stop", "del", "rm"])
        parser.add_command(tracer.toggle_color, prog="color", aliases=["ls"])
        return parser

    def __call__(self, *args, **kwargs):
        spec = kwargs.get("spec")
        usecolor = (
            spec and (spec.captured not in xpp.STDOUT_CAPTURE_KINDS)
        ) and sys.stdout.isatty()
        tracer.color_output(usecolor)
        return super().__call__(*args, **kwargs)


tracermain = TracerAlias()
