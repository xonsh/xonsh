# -*- coding: utf-8 -*-
"""Hooks for Jupyter Xonsh Kernel."""
import builtins
from pprint import pformat
from tempfile import SpooledTemporaryFile

from ipykernel.kernelbase import Kernel

from xonsh import __version__ as version
from xonsh.main import main_context
from xonsh.tools import redirect_stdout, redirect_stderr, swap


MAX_SIZE = 8388608  # 8 Mb

class XonshKernel(Kernel):
    """Xonsh xernal for Jupyter"""
    implementation = 'Xonsh ' + version
    implementation_version = version
    language = 'xonsh'
    language_version = version
    banner = 'Xonsh - the Python-ish, BASHwards-looking shell'
    language_info = {'name': 'xonsh',
                     'pygments_lexer': 'xonsh',
                     'codemirror_mode': 'shell',
                     'mimetype': 'text/x-sh',
                     'file_extension': '.xsh',
                     }

    def do_execute(self, code, silent, store_history=True, user_expressions=None,
                   allow_stdin=False):
        """Execute user code."""
        if len(code.strip()) == 0:
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}
        env = builtins.__xonsh_env__
        shell = builtins.__xonsh_shell__
        hist = builtins.__xonsh_history__
        enc = env.get('XONSH_ENCODING')
        out = SpooledTemporaryFile(max_size=MAX_SIZE, mode='w+t',
                                   encoding=enc, newline='\n')
        err = SpooledTemporaryFile(max_size=MAX_SIZE, mode='w+t',
                                   encoding=enc, newline='\n')
        try:
            with redirect_stdout(out), redirect_stderr(err), \
                 swap(builtins, '__xonsh_stdout_uncaptured__', out), \
                 swap(builtins, '__xonsh_stderr_uncaptured__', err), \
                 env.swap({'XONSH_STORE_STDOUT': False}):
                shell.default(code)
            interrupted = False
        except KeyboardInterrupt:
            interrupted = True

        if not silent:  # stdout response
            if out.tell() > 0:
                out.seek(0)
                self._respond_in_chunks('stdout', out.read())
            if err.tell() > 0:
                err.seek(0)
                self._respond_in_chunks('stderr', err.read())
            if hasattr(builtins, '_') and builtins._ is not None:
                # rely on sys.displayhook functionality
                self._respond_in_chunks('stdout', pformat(builtins._))
                builtins._ = None
            if len(hist) > 0 and out.tell() == 0 and err.tell() == 0:
                self._respond_in_chunks('stdout', hist.outs[-1])

        out.close()
        err.close()

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        rtn = 0 if len(hist) == 0 else hist.rtns[-1]
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
            response = {'name': name, 'text': s[l:u]}
            self.send_response(self.iopub_socket, 'stream', response)

    def do_complete(self, code, pos):
        """Get completions."""
        shell = builtins.__xonsh_shell__
        comps, beg, end = shell.completer.find_and_complete(code, pos, shell.ctx)
        message = {'matches': comps, 'cursor_start': beg, 'cursor_end': end+1,
                   'metadata': {}, 'status': 'ok'}
        return message


if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp
    # must manually pass in args to avoid interfering w/ Jupyter arg parsing
    with main_context(argv=['--shell-type=readline']):
        IPKernelApp.launch_instance(kernel_class=XonshKernel)
