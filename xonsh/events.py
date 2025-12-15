"""
Events for xonsh.

In all likelihood, you want xonsh.built_ins.XSH.events

The best way to "declare" an event is something like::

    __xonsh__.events.doc('on_spam', "Comes with eggs")
"""

import abc
import collections.abc
import inspect

# from xonsh.built_ins import XSH
# from xonsh.tools import print_exception
#

