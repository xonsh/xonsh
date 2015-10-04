"""Hooks for Jupyter Xonsh Kernel."""
import io
import builtins

from ipykernel.kernelbase import Kernel

from xonsh import __version__ as version
from xonsh.main import main_context
from xonsh.tools import redirect_stdout, redirect_stderr


class XonshKernel(Kernel):
    """Xonsh xernal for Jupyter"""
    implementation = 'Xonsh'
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

        shell = builtins.__xonsh_shell__
        hist = builtins.__xonsh_history__
        out = io.StringIO()
        err = io.StringIO()
        try:
            with redirect_stdout(out), redirect_stderr(err):
                shell.default(code)
            interrupted = False
        except KeyboardInterrupt:
            interrupted = True

        if not silent:  # stdout response
            if out.tell() > 0:
                out.seek(0)
                response = {'name': 'stdout', 'text': out.read()}
                self.send_response(self.iopub_socket, 'stream', response)
            if len(hist) > 0:
                response = {'name': 'stdout', 'text': hist.outs[-1]}
                self.send_response(self.iopub_socket, 'stream', response)
            if err.tell() > 0:
                err.seek(0)
                response = {'name': 'stderr', 'text': err.read()}
                self.send_response(self.iopub_socket, 'stream', response)

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

    def  do_complete(self, code, pos):
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
