"""Tools for creating command-line and web-based wizards from a tree of nodes.
"""

class Node(object):
    """Base type of all nodes."""

    attrs = ()


class Wizard(Node):
    """Top-level node in the tree."""

    def __init__(self, children):
        self.children = children


class Pass(Node):
    """Simple do-nothing node"""


class Message(Node):
    """Contains a simple message to report to the user."""

    def __init__(self, message):
        self.message = message


class Question(Node);
    """Asks a question and then chooses the next node based on the response.
    """

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