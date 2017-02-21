"""Implements a xonsh tracer."""
import os
import re
import sys
import inspect
import argparse
import linecache
import importlib
import functools

from xonsh.lazyasd import LazyObject
from xonsh.platform import HAS_PYGMENTS
from xonsh.tools import DefaultNotGiven, print_color, normabspath, to_bool
from xonsh.inspectors import find_file, getouterframes
from xonsh.lazyimps import pygments, pyghooks
from xonsh.proc import STDOUT_CAPTURE_KINDS
import xonsh.prompt.cwd as prompt

terminal = LazyObject(lambda: importlib.import_module(
                                'pygments.formatters.terminal'),
                      globals(), 'terminal')


class TracerType(object):
    """Represents a xonsh tracer object, which keeps track of all tracing
    state. This is a singleton.
    """
    _inst = None
    valid_events = frozenset(['line', 'call'])

    def __new__(cls, *args, **kwargs):
        if cls._inst is None:
            cls._inst = super(TracerType, cls).__new__(cls, *args, **kwargs)
        return cls._inst

    def __init__(self):
        self.prev_tracer = DefaultNotGiven
        self.files = set()
        self.usecolor = True
        self.lexer = pyghooks.XonshLexer()
        self.formatter = terminal.TerminalFormatter()
        self._last = ('', -1)  # filename, lineno tuple

    def __del__(self):
        for f in set(self.files):
            self.stop(f)

    def color_output(self, usecolor):
        """Specify whether or not the tracer output should be colored."""
        # we have to use a function to set usecolor because of the way that
        # lazyasd works. Namely, it cannot dispatch setattr to the target
        # object without being unable to access its own __dict__. This makes
        # setting an atter look like getting a function.
        self.usecolor = usecolor

    def start(self, filename):
        """Starts tracing a file."""
        files = self.files
        if len(files) == 0:
            self.prev_tracer = sys.gettrace()
        files.add(normabspath(filename))
        sys.settrace(self.trace)
        curr = inspect.currentframe()
        for frame, fname, *_ in getouterframes(curr, context=0):
            if normabspath(fname) in files:
                frame.f_trace = self.trace

    def stop(self, filename):
        """Stops tracing a file."""
        filename = normabspath(filename)
        self.files.discard(filename)
        if len(self.files) == 0:
            sys.settrace(self.prev_tracer)
            curr = inspect.currentframe()
            for frame, fname, *_ in getouterframes(curr, context=0):
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
                s = tracer_format_line(fname, lineno, line,
                                       color=self.usecolor,
                                       lexer=self.lexer,
                                       formatter=self.formatter)
                print_color(s)
                self._last = curr
        return self.trace


tracer = LazyObject(TracerType, globals(), 'tracer')

COLORLESS_LINE = '{fname}:{lineno}:{line}'
COLOR_LINE = ('{{PURPLE}}{fname}{{BLUE}}:'
              '{{GREEN}}{lineno}{{BLUE}}:'
              '{{NO_COLOR}}')


def tracer_format_line(fname, lineno, line, color=True, lexer=None, formatter=None):
    """Formats a trace line suitable for printing."""
    fname = min(fname, prompt._replace_home(fname), os.path.relpath(fname),
                key=len)
    if not color:
        return COLORLESS_LINE.format(fname=fname, lineno=lineno, line=line)
    cline = COLOR_LINE.format(fname=fname, lineno=lineno)
    if not HAS_PYGMENTS:
        return cline + line
    # OK, so we have pygments
    tokens = pyghooks.partial_color_tokenize(cline)
    lexer = lexer or pyghooks.XonshLexer()
    tokens += pygments.lex(line, lexer=lexer)
    if tokens[-1][1] == '\n':
        del tokens[-1]
    elif tokens[-1][1].endswith('\n'):
        tokens[-1] = (tokens[-1][0], tokens[-1][1].rstrip())
    return tokens


#
# Command line interface
#

def _find_caller(args):
    """Somewhat hacky method of finding the __file__ based on the line executed."""
    re_line = re.compile(r'[^;\s|&<>]+\s+' + r'\s+'.join(args))
    curr = inspect.currentframe()
    for _, fname, lineno, _, lines, _ in getouterframes(curr, context=1)[3:]:
        if lines is not None and re_line.search(lines[0]) is not None:
            return fname
        elif lineno == 1 and re_line.search(linecache.getline(fname, lineno)) is not None:
            # There is a bug in CPython such that getouterframes(curr, context=1)
            # will actually return the 2nd line in the code_context field, even though
            # line number is itself correct. We manually fix that in this branch.
            return fname
    else:
        msg = ('xonsh: warning: __file__ name could not be found. You may be '
               'trying to trace interactively. Please pass in the file names '
               'you want to trace explicitly.')
        print(msg, file=sys.stderr)


def _on(ns, args):
    """Turns on tracing for files."""
    for f in ns.files:
        if f == '__file__':
            f = _find_caller(args)
        if f is None:
            continue
        tracer.start(f)


def _off(ns, args):
    """Turns off tracing for files."""
    for f in ns.files:
        if f == '__file__':
            f = _find_caller(args)
        if f is None:
            continue
        tracer.stop(f)


def _color(ns, args):
    """Manages color action for tracer CLI."""
    tracer.color_output(ns.toggle)


@functools.lru_cache(1)
def _tracer_create_parser():
    """Creates tracer argument parser"""
    p = argparse.ArgumentParser(prog='trace',
                                description='tool for tracing xonsh code as it runs.')
    subp = p.add_subparsers(title='action', dest='action')
    onp = subp.add_parser('on', aliases=['start', 'add'],
                          help='begins tracing selected files.')
    onp.add_argument('files', nargs='*', default=['__file__'],
                     help=('file paths to watch, use "__file__" (default) to select '
                           'the current file.'))
    off = subp.add_parser('off', aliases=['stop', 'del', 'rm'],
                          help='removes selected files fom tracing.')
    off.add_argument('files', nargs='*', default=['__file__'],
                     help=('file paths to stop watching, use "__file__" (default) to '
                           'select the current file.'))
    col = subp.add_parser('color', help='output color management for tracer.')
    col.add_argument('toggle', type=to_bool,
                     help='true/false, y/n, etc. to toggle color usage.')
    return p


_TRACER_MAIN_ACTIONS = {
    'on': _on,
    'add': _on,
    'start': _on,
    'rm': _off,
    'off': _off,
    'del': _off,
    'stop': _off,
    'color': _color,
    }


def tracermain(args=None, stdin=None, stdout=None, stderr=None, spec=None):
    """Main function for tracer command-line interface."""
    parser = _tracer_create_parser()
    ns = parser.parse_args(args)
    usecolor = ((spec.captured not in STDOUT_CAPTURE_KINDS) and
                sys.stdout.isatty())
    tracer.color_output(usecolor)
    return _TRACER_MAIN_ACTIONS[ns.action](ns, args)
