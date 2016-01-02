"""Tools for creating command-line and web-based wizards from a tree of nodes.
"""
import textwrap
from pprint import pformat

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

    attrs = ('children',)

    def __init__(self, children):
        self.children = children


class Pass(Node):
    """Simple do-nothing node"""


class Message(Node):
    """Contains a simple message to report to the user."""

    attrs = ('message',)

    def __init__(self, message):
        self.message = message


class Question(Node):
    """Asks a question and then chooses the next node based on the response.
    """

    attrs = ('question', 'responses')

    def __init__(self, question, responses):
        """
        Parameters
        ----------
        question : str
            The question itself.
        responses : dict with str keys and Node values
            Mapping from user-input responses to nodes.
        """
        self.question = question
        self.responses = responses


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
            return s + '])'
        s += '\n'
        self.level += 1
        s += textwrap.indent(',\n'.join(map(self.visit, node.children)), 
                             self.indent)
        self.level -= 1
        s += '\n])'
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
        self.level -= 1
        s += '\n)'
        return s


