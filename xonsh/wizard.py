"""Tools for creating command-line and web-based wizards from a tree of nodes.
"""
import ast
import builtins
import textwrap
from pprint import pformat
from collections.abc import MutableSequence, Mapping, Sequence

#
# Nodes themselves 
#

class Node(object):
    """Base type of all nodes."""

    attrs = ()

    def __str__(self):
        return PrettyFormatter(self).visit()

    def __repr__(self):
        return str(self).replace('\n', '')


class Wizard(Node):
    """Top-level node in the tree."""

    attrs = ('children', 'path')

    def __init__(self, children, path=None):
        self.children = children
        self.path = None


class Pass(Node):
    """Simple do-nothing node"""


class Message(Node):
    """Contains a simple message to report to the user."""

    attrs = ('message')

    def __init__(self, message):
        self.message = message


class Question(Node):
    """Asks a question and then chooses the next node based on the response.
    """

    attrs = ('question', 'responses', 'path')

    def __init__(self, question, responses, path=None):
        """
        Parameters
        ----------
        question : str
            The question itself.
        responses : dict with str keys and Node values
            Mapping from user-input responses to nodes.
        path : str or sequence of str
            A path within the storage object.
        """
        self.question = question
        self.responses = responses
        self.path = None


#
# Tools for trees of nodes.
# 

_lowername = lambda cls: cls.__name__.lower()

class Visitor(object):
    """Super-class for all classes that should walk over a tree of nodes.
    This implements the visit() method.
    """

    def __init__(self, tree=None):
        self.tree = tree

    def visit(self, node=None):
        """Walks over a node.  If no node is provided, the tree is used."""
        if node is None:
            node = self.tree
        if node is None:
            raise RuntimeError('no node or tree given!')
        for clsname in map(_lowername, type.mro(node.__class__)):
            meth = getattr(self, 'visit_' + clsname, None)
            if callable(meth):
                rtn = meth(node)
                break
        else:
            msg = 'could not find valid visitor method for {0} on {1}'
            nodename = node.__class__.__name__ 
            selfname = self.__class__.__name__
            raise AttributeError(msg.format(nodename, selfname))
        return rtn
                

class PrettyFormatter(Visitor):
    """Formats a tree of nodes into a pretty string"""

    def __init__(self, tree=None, indent=' '):
        super().__init__(tree=tree)
        self.level = 0
        self.indent = indent

    def visit_node(self, node):
        s = node.__class__.__name__ + '('
        if len(node.attrs) == 0:
            return s + ')'
        s += '\n'
        self.level += 1
        t = []
        for aname in node.attrs:
            a = getattr(node, aname)
            t.append(self.visit(a) if isinstance(a, Node) else pformat(a))
        t = ['{0}={1}'.format(n, x) for n, x in zip(node.attrs, t)]
        s += textwrap.indent(',\n'.join(t), self.indent)
        self.level -= 1
        s += '\n)'
        return s

    def visit_wizard(self, node):
        s = 'Wizard(children=['
        if len(node.children) == 0:
            if node.path is None:
                return s + '])'
            else:
                return s + '], path={0!r})'.format(node.path)
        s += '\n'
        self.level += 1
        s += textwrap.indent(',\n'.join(map(self.visit, node.children)), 
                             self.indent)
        self.level -= 1
        if node.path is None:
            s += '\n])'
        else:
            s += '{0}],\n{0}path={1!r}\n)'.format(self.indent, node.path)
        return s

    def visit_message(self, node):
        return 'Message({0!r})'.format(node.message)

    def visit_question(self, node):
        s = 'Question(\n'
        self.level += 1
        s += self.indent + 'question={0!r},\n'.format(node.question)
        s += self.indent + 'responses={'
        if len(node.responses) == 0:
            s += '}'
        else:
            s += '\n'
            t = sorted(node.responses.items())
            t = ['{0!r}: {1}'.format(k, self.visit(v)) for k, v in t]
            s += textwrap.indent(',\n'.join(t), 2*self.indent) 
            s += '\n' + self.indent + '}'
        if node.path is not None:
            s += ',\n' + self.indent + 'path={0!r}'.format(node.path)
        self.level -= 1
        s += '\n)'
        return s


def ensure_str_or_int(x):
    """Creates a string or int."""
    if isinstance(x, int):
        return x
    x = x if isinstance(x, str) else str(x)
    try:
        x = ast.literal_eval(x)
    except (ValueError, SyntaxError):
        pass
    if not isinstance(x, (int, str)):
        msg = '{0!r} could not be converted to int or str'.format(x)
        raise ValueError(msg)
    return x


def canon_path(path):
    """Returns the canonical form of a path, which is a tuple of str or ints."""
    if not isinstance(path, str):
        return tuple(map(ensure_str_or_int, path))
    path = path[1:] if path.startswith('/') else path
    path = path[:-1] if path.endswith('/') else path
    if len(path) == 0:
        return ()
    return tuple(map(ensure_str_or_int, path.split('/')))


class StateVisitor(Visitor):
    """This class visits the nodes and stores the results in a top-level
    dict of data according to the state path of the node. The the node
    does not have a path or the path does not exist, the storage is skipped.
    This class can be optionally initialized with an existing state.
    """

    def __init__(self, tree=None, state=None):
        super().__init__(tree=tree)
        self.state = {} if state is None else state

    def visit(self, node=None):
        if node is None:
            node = self.tree
        if node is None:
            raise RuntimeError('no node or tree given!')
        rtn = super().visit(node)
        path = getattr(node, 'path', None)
        if path is not None:
            self.store(path, rtn)            
        return rtn

    def store(self, path, val):
        """Stores a value at the path location."""
        path = canon_path(path)
        loc = self.state
        for p, n in zip(path[:-1], path[1:]):
            if isinstance(p, str) and p not in loc:
                loc[p] = {} if isinstance(n, str) else []
            elif isinstance(p, int) and abs(p) + (p >= 0) > len(loc):
                i = abs(p) + (p >= 0) - len(loc)
                if isinstance(n, str):
                    ex = [{} for _ in range(i)]
                else:
                    ex = [[] for _ in range(i)]
                loc.extend(ex)
            loc = loc[p]
        p = path[-1]
        loc[p] = val


class PromptVisitor(StateVisitor):
    """Visits the nodes in the tree via the a command-line prompt."""

    def __init__(self, tree=None, state=None):
        super().__init__(tree=tree, state=state)
        self.env = builtins.__xonsh_env__
        self.shell = builtins.__xonsh_shell__.shell

    def visit_wizard(self, node):
        for child in node.children:
            self.visit(child)

    def visit_pass(self, node):
        pass

    def visit_message(self, node):
        print(node.message)

    def visit_question(self, node):
        self.env['PROMPT'] = node.question
        r = self.shell.singleline()
        self.visit(node.responses[r])
        return r
