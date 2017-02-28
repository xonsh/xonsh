"""Tools for creating command-line and web-based wizards from a tree of nodes.
"""
import os
import ast
import json
import pprint
import builtins
import textwrap

from xonsh.tools import to_bool, to_bool_or_break, backup_file, print_color
from xonsh.jsonutils import serialize_xonsh_json


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
        self.path = path


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

    attrs = ('question', 'responses', 'converter', 'path')

    def __init__(self, question, responses, converter=None, path=None):
        """
        Parameters
        ----------
        question : str
            The question itself.
        responses : dict with str keys and Node values
            Mapping from user-input responses to nodes.
        converter : callable, optional
            Converts the string the user typed into another object
            that serves as a key to the reponses dict.
        path : str or sequence of str, optional
            A path within the storage object.
        """
        self.question = question
        self.responses = responses
        self.converter = converter
        self.path = path


class Input(Node):
    """Gets input from the user."""

    attrs = ('prompt', 'converter', 'show_conversion', 'confirm', 'path')

    def __init__(self, prompt='>>> ', converter=None, show_conversion=False,
                 confirm=False, retry=False, path=None):
        """
        Parameters
        ----------
        prompt : str, optional
            Prompt string prior to input
        converter : callable, optional
            Converts the string the user typed into another object
            prior to storage.
        show_conversion : bool, optional
            Flag for whether or not to show the results of the conversion
            function if the conversion function was meaningfully executed.
            Default False.
        confirm : bool, optional
            Whether the input should be confirmed until true or broken,
            default False.
        retry : bool, optional
            In the event that the conversion operation fails, should
            users be re-prompted until they provide valid input. Deafult False.
        path : str or sequence of str, optional
            A path within the storage object.
        """
        self.prompt = prompt
        self.converter = converter
        self.show_conversion = show_conversion
        self.confirm = confirm
        self.retry = retry
        self.path = path


class While(Node):
    """Computes a body while a condition function evaluates to true.
    The condition function has the form cond(visitor=None, node=None) and
    should return an object that is convertable to a bool. The beg attribute
    specifies the number to start the loop iteration at.
    """

    attrs = ('cond', 'body', 'idxname', 'beg', 'path')

    def __init__(self, cond, body, idxname='idx', beg=0, path=None):
        """
        Parameters
        ----------
        cond : callable
            Function that determines if the next loop iteration should
            be executed. The condition function has the form
            cond(visitor=None, node=None) and should return an object that
            is convertable to a bool.
        body : sequence of nodes
            A list of node to execute on each iteration.
        idxname : str, optional
            The variable name for the index.
        beg : int, optional
            The first index value when evaluating path format strings.
        path : str or sequence of str, optional
            A path within the storage object.
        """
        self.cond = cond
        self.body = body
        self.idxname = idxname
        self.beg = beg
        self.path = path


#
# Helper nodes
#

class YesNo(Question):
    """Represents a simple yes/no question."""

    def __init__(self, question, yes, no, path=None):
        """
        Parameters
        ----------
        question : str
            The question itself.
        yes : Node
            Node to execute if the response is True.
        no : Node
            Node to execute if the response is False.
        path : str or sequence of str, optional
            A path within the storage object.
        """
        responses = {True: yes, False: no}
        super().__init__(question, responses, converter=to_bool,
                         path=path)


class TrueFalse(Input):
    """Input node the returns a True or False value."""

    def __init__(self, prompt='yes or no [default: no]? ', path=None):
        super().__init__(prompt=prompt, converter=to_bool,
                         show_conversion=False, confirm=False, path=path)


class TrueFalseBreak(Input):
    """Input node the returns a True, False, or 'break' value."""

    def __init__(self, prompt='yes, no, or break [default: no]? ', path=None):
        super().__init__(prompt=prompt, converter=to_bool_or_break,
                         show_conversion=False, confirm=False, path=path)


class StoreNonEmpty(Input):
    """Stores the user input only if the input was not an empty string.
    This works by wrapping the converter function.
    """

    def __init__(self, prompt='>>> ', converter=None, show_conversion=False,
                 confirm=False, retry=False, path=None, store_raw=False):
        def nonempty_converter(x):
            """Converts non-empty values and converts empty inputs to
            Unstorable.
            """
            if len(x) == 0:
                x = Unstorable
            elif converter is None:
                pass
            elif store_raw:
                converter(x)  # make sure str is valid, even if storing raw
            else:
                x = converter(x)
            return x
        super().__init__(prompt=prompt, converter=nonempty_converter,
                         show_conversion=show_conversion, confirm=confirm,
                         path=path, retry=retry)


class StateFile(Input):
    """Node for repesenting the state as a JSON file under a default or user
    given file name. This node type is likely not useful on its own.
    """

    attrs = ('default_file', 'check', 'ask_filename')

    def __init__(self, default_file=None, check=True, ask_filename=True):
        """
        Parameters
        ----------
        default_file : str, optional
            The default filename to save the file as.
        check : bool, optional
            Whether to print the current state and ask if it should be
            saved/loaded prior to asking for the file name and saving the
            file, default=True.
        ask_filename : bool, optional
            Whether to ask for the filename (if ``False``, always use the
            default filename)
        """
        self._df = None
        super().__init__(prompt='filename: ', converter=None,
                         confirm=False, path=None)
        self.ask_filename = ask_filename
        self.default_file = default_file
        self.check = check

    @property
    def default_file(self):
        return self._df

    @default_file.setter
    def default_file(self, val):
        self._df = val
        if val is None:
            self.prompt = 'filename: '
        else:
            self.prompt = 'filename [default={0!r}]: '.format(val)


class Save(StateFile):
    """Node for saving the state as a JSON file under a default or user
    given file name.
    """


class Load(StateFile):
    """Node for loading the state as a JSON file under a default or user
    given file name.
    """


def create_truefalse_cond(prompt='yes or no [default: no]? ', path=None):
    """This creates a basic condition function for use with nodes like While
    or other conditions. The condition function creates and visits a TrueFalse
    node and returns the result. This TrueFalse node takes the prompt and
    path that is passed in here.
    """
    def truefalse_cond(visitor, node=None):
        """Prompts the user for a true/false condition."""
        tf = TrueFalse(prompt=prompt, path=path)
        rtn = visitor.visit(tf)
        return rtn
    return truefalse_cond


#
# Tools for trees of nodes.
#


def _lowername(cls):
    return cls.__name__.lower()


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
            t.append(self.visit(a) if isinstance(a, Node) else pprint.pformat(a))
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
        s = node.__class__.__name__ + '(\n'
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
        if node.converter is not None:
            s += ',\n' + self.indent + 'converter={0!r}'.format(node.converter)
        if node.path is not None:
            s += ',\n' + self.indent + 'path={0!r}'.format(node.path)
        self.level -= 1
        s += '\n)'
        return s

    def visit_input(self, node):
        s = '{0}(prompt={1!r}'.format(node.__class__.__name__, node.prompt)
        if node.converter is None and node.path is None:
            return s + '\n)'
        if node.converter is not None:
            s += ',\n' + self.indent + 'converter={0!r}'.format(node.converter)
        s += ',\n' + self.indent + 'show_conversion={0!r}'.format(node.show_conversion)
        s += ',\n' + self.indent + 'confirm={0!r}'.format(node.confirm)
        s += ',\n' + self.indent + 'retry={0!r}'.format(node.retry)
        if node.path is not None:
            s += ',\n' + self.indent + 'path={0!r}'.format(node.path)
        s += '\n)'
        return s

    def visit_statefile(self, node):
        s = '{0}(default_file={1!r}, check={2}, ask_filename={3})'
        s = s.format(node.__class__.__name__, node.default_file, node.check, node.ask_filename)
        return s

    def visit_while(self, node):
        s = '{0}(cond={1!r}'.format(node.__class__.__name__, node.cond)
        s += ',\n' + self.indent + 'body=['
        if len(node.body) > 0:
            s += '\n'
            self.level += 1
            s += textwrap.indent(',\n'.join(map(self.visit, node.body)),
                                 self.indent)
            self.level -= 1
            s += '\n' + self.indent
        s += ']'
        s += ',\n' + self.indent + 'idxname={0!r}'.format(node.idxname)
        s += ',\n' + self.indent + 'beg={0!r}'.format(node.beg)
        if node.path is not None:
            s += ',\n' + self.indent + 'path={0!r}'.format(node.path)
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


def canon_path(path, indices=None):
    """Returns the canonical form of a path, which is a tuple of str or ints.
    Indices may be optionally passed in.
    """
    if not isinstance(path, str):
        return tuple(map(ensure_str_or_int, path))
    if indices is not None:
        path = path.format(**indices)
    path = path[1:] if path.startswith('/') else path
    path = path[:-1] if path.endswith('/') else path
    if len(path) == 0:
        return ()
    return tuple(map(ensure_str_or_int, path.split('/')))


class UnstorableType(object):
    """Represents an unstorable return value for when no input was given
    or such input was skipped. Typically represented by the Unstorable
    singleton.
    """

    _inst = None

    def __new__(cls, *args, **kwargs):
        if cls._inst is None:
            cls._inst = super(UnstorableType, cls).__new__(cls, *args,
                                                           **kwargs)
        return cls._inst


Unstorable = UnstorableType()


class StateVisitor(Visitor):
    """This class visits the nodes and stores the results in a top-level
    dict of data according to the state path of the node. The the node
    does not have a path or the path does not exist, the storage is skipped.
    This class can be optionally initialized with an existing state.
    """

    def __init__(self, tree=None, state=None, indices=None):
        super().__init__(tree=tree)
        self.state = {} if state is None else state
        self.indices = {} if indices is None else indices

    def visit(self, node=None):
        if node is None:
            node = self.tree
        if node is None:
            raise RuntimeError('no node or tree given!')
        rtn = super().visit(node)
        path = getattr(node, 'path', None)
        if callable(path):
            path = path(visitor=self, node=node, val=rtn)
        if path is not None and rtn is not Unstorable:
            self.store(path, rtn, indices=self.indices)
        return rtn

    def store(self, path, val, indices=None):
        """Stores a value at the path location."""
        path = canon_path(path, indices=indices)
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
        if isinstance(p, int) and abs(p) + (p >= 0) > len(loc):
            i = abs(p) + (p >= 0) - len(loc)
            ex = [None]*i
            loc.extend(ex)
        loc[p] = val


YN = "{GREEN}yes{NO_COLOR} or {RED}no{NO_COLOR} [default: no]? "
YNB = ('{GREEN}yes{NO_COLOR}, {RED}no{NO_COLOR}, or '
       '{YELLOW}break{NO_COLOR} [default: no]? ')


class PromptVisitor(StateVisitor):
    """Visits the nodes in the tree via the a command-line prompt."""

    def __init__(self, tree=None, state=None, **kwargs):
        """
        Parameters
        ----------
        tree : Node, optional
            Tree of nodes to start visitor with.
        state : dict, optional
            Initial state to begin with.
        kwargs : optional
            Options that are passed through to the prompt via the shell's
            singleline() method. See BaseShell for mor details.
        """
        super().__init__(tree=tree, state=state)
        self.env = builtins.__xonsh_env__
        self.shell = builtins.__xonsh_shell__.shell
        self.shell_kwargs = kwargs

    def visit_wizard(self, node):
        for child in node.children:
            self.visit(child)

    def visit_pass(self, node):
        pass

    def visit_message(self, node):
        print_color(node.message)

    def visit_question(self, node):
        self.env['PROMPT'] = node.question
        r = self.shell.singleline(**self.shell_kwargs)
        if callable(node.converter):
            r = node.converter(r)
        self.visit(node.responses[r])
        return r

    def visit_input(self, node):
        need_input = True
        while need_input:
            self.env['PROMPT'] = node.prompt
            raw = self.shell.singleline(**self.shell_kwargs)
            if callable(node.converter):
                try:
                    x = node.converter(raw)
                except KeyboardInterrupt:
                    raise
                except Exception:
                    if node.retry:
                        msg = ('{{BOLD_RED}}Invalid{{NO_COLOR}} input {0!r}, '
                               'please retry.')
                        print_color(msg.format(raw))
                        continue
                    else:
                        raise
                if node.show_conversion and x is not Unstorable \
                        and str(x) != raw:
                    msg = '{{BOLD_PURPLE}}Converted{{NO_COLOR}} input {0!r} to {1!r}.'
                    print_color(msg.format(raw, x))
            else:
                x = raw
            if node.confirm:
                msg = 'Would you like to keep the input: {0}'
                print(msg.format(pprint.pformat(x)))
                confirmer = TrueFalseBreak(prompt=YNB)
                status = self.visit(confirmer)
                if isinstance(status, str) and status == 'break':
                    x = Unstorable
                    break
                else:
                    need_input = not status
            else:
                need_input = False
        return x

    def visit_while(self, node):
        rtns = []
        origidx = self.indices.get(node.idxname, None)
        self.indices[node.idxname] = idx = node.beg
        while node.cond(visitor=self, node=node):
            rtn = list(map(self.visit, node.body))
            rtns.append(rtn)
            idx += 1
            self.indices[node.idxname] = idx
        if origidx is None:
            del self.indices[node.idxname]
        else:
            self.indices[node.idxname] = origidx
        return rtns

    def visit_save(self, node):
        jstate = json.dumps(self.state, indent=1, sort_keys=True,
                            default=serialize_xonsh_json)
        if node.check:
            msg = 'The current state is:\n\n{0}\n'
            print(msg.format(textwrap.indent(jstate, '    ')))
            ap = 'Would you like to save this state, ' + YN
            asker = TrueFalse(prompt=ap)
            do_save = self.visit(asker)
            if not do_save:
                return Unstorable
        fname = None
        if node.ask_filename:
            fname = self.visit_input(node)
        if fname is None or len(fname) == 0:
            fname = node.default_file
        if os.path.isfile(fname):
            backup_file(fname)
        else:
            os.makedirs(os.path.dirname(fname), exist_ok=True)
        with open(fname, 'w') as f:
            f.write(jstate)
        return fname

    def visit_load(self, node):
        if node.check:
            ap = 'Would you like to load an existing file, ' + YN
            asker = TrueFalse(prompt=ap)
            do_load = self.visit(asker)
            if not do_load:
                return Unstorable
        fname = self.visit_input(node)
        if fname is None or len(fname) == 0:
            fname = node.default_file
        if os.path.isfile(fname):
            with open(fname, 'r') as f:
                self.state = json.load(f)
            print_color('{{GREEN}}{0!r} loaded.{{NO_COLOR}}'.format(fname))
        else:
            print_color(('{{RED}}{0!r} could not be found, '
                         'continuing.{{NO_COLOR}}').format(fname))
        return fname
