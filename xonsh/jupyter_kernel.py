# -*- coding: utf-8 -*-
"""Hooks for Jupyter Xonsh Kernel."""
import builtins
from pprint import pformat

from ipykernel.kernelbase import Kernel

from xonsh import __version__ as version
from xonsh.main import main_context
from xonsh.completer import Completer


MAX_SIZE = 8388608  # 8 Mb


class XonshKernel(Kernel):
    """Xonsh xernal for Jupyter"""
    implementation = 'Xonsh ' + version
    implementation_version = version
    language = 'xonsh'
    language_version = version
    banner = 'Xonsh - Python-powered, cross-platform shell'
    language_info = {'name': 'xonsh',
                     'version': version,
                     'pygments_lexer': 'xonsh',
                     'codemirror_mode': 'shell',
                     'mimetype': 'text/x-sh',
                     'file_extension': '.xsh',
                     }

    def __init__(self, **kwargs):
        self.completer = Completer()
        super().__init__(**kwargs)

    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        """Execute user code."""
        if len(code.strip()) == 0:
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}
        shell = builtins.__xonsh_shell__
        hist = builtins.__xonsh_history__
        try:
            shell.default(code)
            interrupted = False
        except KeyboardInterrupt:
            interrupted = True

        if not silent:  # stdout response
            if hasattr(builtins, '_') and builtins._ is not None:
                # rely on sys.displayhook functionality
                self._respond_in_chunks('stdout', pformat(builtins._))
                builtins._ = None
            if hist is not None and len(hist) > 0:
                self._respond_in_chunks('stdout', hist.outs[-1])

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        rtn = 0 if (hist is None or len(hist) == 0) else hist.rtns[-1]
        if 0 < rtn:
            message = {'status': 'error', 'execution_count': self.execution_count,
                       'ename': '', 'evalue': str(rtn), 'traceback': []}
        else:
            message = {'status': 'ok', 'execution_count': self.execution_count,
                       'payload': [], 'user_expressions': {}}
        return message

    def _respond_in_chunks(self, name, s, chunksize=1024):
        if s is None:
            return
        n = len(s)
        if n == 0:
            return
        lower = range(0, n, chunksize)
        upper = range(chunksize, n+chunksize, chunksize)
        for l, u in zip(lower, upper):
            response = {'name': name, 'text': s[l:u], }
            self.send_response(self.iopub_socket, 'stream', response)

    def do_complete(self, code, pos):
        """Get completions."""
        shell = builtins.__xonsh_shell__
        line = code.split('\n')[-1]
        line = builtins.aliases.expand_alias(line)
        prefix = line.split(' ')[-1]
        endidx = pos
        begidx = pos - len(prefix)
        rtn, _ = self.completer.complete(prefix, line, begidx,
                                         endidx, shell.ctx)
        message = {'matches': rtn, 'cursor_start': begidx, 'cursor_end': endidx,
                   'metadata': {}, 'status': 'ok'}
        return message


if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp
    # must manually pass in args to avoid interfering w/ Jupyter arg parsing
    with main_context(argv=['--shell-type=readline']):
        IPKernelApp.launch_instance(kernel_class=XonshKernel)
