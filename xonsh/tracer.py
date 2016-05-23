"""Implements a xonsh tracer."""
import os
import re
import sys
import inspect
import linecache
from functools import lru_cache
from argparse import ArgumentParser

from xonsh.tools import DefaultNotGiven, print_color, normabspath, to_bool
from xonsh.platform import HAS_PYGMENTS
from xonsh import inspectors
from xonsh.environ import _replace_home as replace_home

if HAS_PYGMENTS:
    from xonsh import pyghooks
    import pygments
    import pygments.formatters.terminal


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
        self.formatter = pygments.formatters.terminal.TerminalFormatter()
        self._last = ('', -1)  # filename, lineno tuple

    def __del__(self):
        for f in set(self.files):
            self.stop(f)

    def start(self, filename):
        """Starts tracing a file."""
        files = self.files
        if len(files) == 0:
            self.prev_tracer = sys.gettrace()
        files.add(normabspath(filename))
        sys.settrace(self.trace)
        curr = inspect.currentframe()
        for frame, fname, *_ in inspectors.getouterframes(curr, context=0):
            if normabspath(fname) in files:
                frame.f_trace = self.trace

    def stop(self, filename):
        """Stops tracing a file."""
        filename = normabspath(filename)
        self.files.discard(filename)
        if len(self.files) == 0:
            sys.settrace(self.prev_tracer)
            curr = inspect.currentframe()
            for frame, fname, *_ in inspectors.getouterframes(curr, context=0):
                if normabspath(fname) == filename:
                    frame.f_trace = self.prev_tracer
            self.prev_tracer = DefaultNotGiven

    def trace(self, frame, event, arg):
        """Implements a line tracing function."""
        if event not in self.valid_events:
            return self.trace
        fname = inspectors.find_file(frame)
        if fname in self.files:
            lineno = frame.f_lineno
            curr = (fname, lineno)
            if curr != self._last:
                line = linecache.getline(fname, lineno).rstrip()
                s = format_line(fname, lineno, line, color=self.usecolor,
                                lexer=self.lexer, formatter=self.formatter)
                print_color(s)
                self._last = curr
        return self.trace


tracer = TracerType()

COLORLESS_LINE = '{fname}:{lineno}:{line}'
COLOR_LINE = ('{{PURPLE}}{fname}{{BLUE}}:'
              '{{GREEN}}{lineno}{{BLUE}}:'
              '{{NO_COLOR}}')


def format_line(fname, lineno, line, color=True, lexer=None, formatter=None):
    """Formats a trace line suitable for printing."""
    fname = min(fname, replace_home(fname), os.path.relpath(fname), key=len)
    if not color:
        return COLORLESS_LINE.format(fname=fname, lineno=lineno, line=line)
    cline = COLOR_LINE.format(fname=fname, lineno=lineno)
    if not HAS_PYGMENTS:
        return cline + line
    # OK, so we have pygments
    tokens = pyghooks.partial_color_tokenize(cline)
    lexer = lexer or pyghooks.XonshLexer()
    tokens += pygments.lex(line, lexer=lexer)
    return tokens


#
# Command line interface
#

def _find_caller(args):
    """Somewhat hacky method of finding the __file__ based on the line executed."""
    re_line = re.compile(r'[^;\s|&<>]+\s+' + r'\s+'.join(args))
    curr = inspect.currentframe()
    for _, fname, lineno, _, lines, _ in inspectors.getouterframes(curr, context=1)[3:]:
        if lines is not None and re_line.search(lines[0]) is not None:
            return fname
        elif lineno == 1 and re_line.search(linecache.getline(fname, lineno)) is not None:
            # There is a bug in CPython such that inspectors.getouterframes(curr, context=1)
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
    tracer.usecolor = ns.toggle


@lru_cache()
def _create_parser():
    """Creates tracer argument parser"""
    p = ArgumentParser(prog='trace',
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


_MAIN_ACTIONS = {
    'on': _on,
    'add': _on,
    'start': _on,
    'rm': _off,
    'off': _off,
    'del': _off,
    'stop': _off,
    'color': _color,
    }


def main(args=None):
    """Main function for tracer command-line interface."""
    parser = _create_parser()
    ns = parser.parse_args(args)
    return _MAIN_ACTIONS[ns.action](ns, args)


if __name__ == '__main__':
    main()
