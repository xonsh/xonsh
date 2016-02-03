"""Implements a xonsh tracer."""
import os
import sys
import inspect
import linecache    

from xonsh.tools import DefaultNotGiven, print_color, pygments_version, normabspath
from xonsh import inspectors
if pygments_version():
    from xonsh import pyghooks
    import pygments
    import pygments.formatters.terminal
else:
    pyghooks = None
from xonsh.environ import _replace_home as replace_home

class TracerType(object):
    """Represents a xonsh tracer object, which keeps track of all tracing
    state. This is a singleton.
    """

    _inst = None
    valid_events = frozenset(['line', 'call'])

    def __new__(cls, *args, **kwargs):
        if cls._inst is None:
            cls._inst = super(TracerType, cls).__new__(cls, *args, 
                                                           **kwargs)
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
        fname = inspectors.find_file(frame)
        if fname in self.files:
            lineno = frame.f_lineno
            curr = (fname, lineno)
            if curr != self._last:
                line = linecache.getline(fname, lineno).rstrip()
                s = format_line(fname, lineno, line, color=self.usecolor,
                                lexer=self.lexer, formatter=self.formatter).rstrip()
                print_color(s)
                self._last = curr
        return self.trace


tracer = TracerType()

COLORLESS_LINE = '{fname}:{lineno}:{line}'
COLOR_LINE = ('{{PURPLE}}{fname}{{BLUE}}:'
              '{{GREEN}}{lineno}{{BLUE}}:'
              '{{NO_COLOR}}{line}')

def format_line(fname, lineno, line, color=True, lexer=None, formatter=None):
    """Formats a trace line suitable for printing."""
    fname = min(fname, replace_home(fname), os.path.relpath(fname), key=len)
    if not color:
        return COLORLESS_LINE.format(fname=fname, lineno=lineno, line=line)
    if pyghooks is not None:
        lexer = lexer or pyghooks.XonshLexer()
        formatter = formatter or pygments.formatters.terminal.TerminalFormatter()
        line = pygments.highlight(line, lexer, formatter)
    return COLOR_LINE.format(fname=fname, lineno=lineno, line=line)
