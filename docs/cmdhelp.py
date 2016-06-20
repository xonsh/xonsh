"""This module adds a reST directive to sphinx that generates alias
documentation. For example::

    .. command-help:: xonsh.aliases.source_foreign

    .. command-help:: xonsh.aliases.source_foreign -h

will create help for aliases.
"""
import io
import textwrap
import importlib
from docutils import nodes, statemachine, utils
try:
    from docutils.utils.error_reporting import ErrorString  # the new way
except ImportError:
    from docutils.error_reporting import ErrorString        # the old way
from docutils.parsers.rst import Directive, convert_directive_function
from docutils.parsers.rst import directives, roles, states
from docutils.parsers.rst.roles import set_classes
from docutils.transforms import misc
from docutils.statemachine import ViewList

from sphinx.util.nodes import nested_parse_with_titles

from xonsh.tools import redirect_stdout, redirect_stderr


class CommandHelp(Directive):
    """The command-help directive, which is based on constructing a list of
    of string lines of restructured text and then parsing it into its own node.
    Note that this will add the '--help' flag automatically.
    """
    required_arguments = 1
    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = {}
    has_content = False

    def run(self):
        arguments = self.arguments
        lines = ['.. code-block:: none', '']
        m, f = arguments[0].rsplit('.',  1)
        mod = importlib.import_module(m)
        func = getattr(mod, f)
        args = ['--help'] if len(arguments) == 1 else arguments[1:]
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                func(args)
            except SystemExit:
                pass
        stdout.seek(0)
        s = stdout.read()
        lines += textwrap.indent(s, '    ').splitlines()

        # hook to docutils
        src, lineno = self.state_machine.get_source_and_line(self.lineno)
        vl = ViewList(lines, source=src)
        node = nodes.paragraph()
        nested_parse_with_titles(self.state, vl, node)
        return node.children


def setup(app):
    app.add_directive('command-help', CommandHelp)

