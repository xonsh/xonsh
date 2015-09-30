"""Hooks for Jupyter Xonsh Kernel."""
import builtins

from ipykernel.kernelbase import Kernel

from xonsh import __version__ as version
from xonsh.main import main_context


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
        try:
            shell.default(code)
            interrupted = False
        except KeyboardInterrupt:
            interrupted = True

        if not silent:  # stdout response
            response = {'name': 'stdout', 'text': hist.outs[-1]}
            self.send_response(self.iopub_socket, 'stream', response)

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        rtn = hist.rtns[-1]
        if 0 < rtn:
            message = {'status': 'error', 'execution_count': self.execution_count,
                       'ename': '', 'evalue': str(rtn), 'traceback': []}
        else:
            message = {'status': 'ok', 'execution_count': self.execution_count,
                       'payload': [], 'user_expressions': {}}
        return message


if __name__ == '__main__':
    from ipykernel.kernelapp import IPKernelApp
    # must manually pass in args to avoid interfering w/ Jupyter arg parsing
    with main_context(argv=[]):
        IPKernelApp.launch_instance(kernel_class=XonshKernel)
