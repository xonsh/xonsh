"""Hooks for Jupyter Xonsh Kernel."""

from IPython.kernel.zmq.kernelbase import Kernel

from xonsh import __version__ as version
from xonsh.main import main_generator


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._xonsh_main = main_generator()
        self._xonsh_shell = next(self._xonsh_main)

    def __del__(self):
        next(self._xonsh_main)
        super().__del__()

    def do_execute(self, code, silent, store_history=True, user_expressions=None, 
                   allow_stdin=False):
        """Execute user code."""
