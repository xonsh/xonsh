"""Main entry points of the xonsh history."""

import sys

import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.history.base import History
from xonsh.history.dummy import DummyHistory
from xonsh.history.json import JsonHistory

HISTORY_BACKENDS = {"dummy": DummyHistory, "json": JsonHistory}

try:
    from xonsh.history.sqlite import SqliteHistory

    HISTORY_BACKENDS |= {"sqlite": SqliteHistory}
except Exception:
    """
    On some linux systems (e.g. alt linux) sqlite3 is not installed
    and it's hard to install it and maybe user can't install it.
    We need to just go forward.
    """
    pass


def construct_history(backend=None, **kwargs) -> "History":
    """Construct the history backend object."""
    env = XSH.env
    backend = backend or env.get("XONSH_HISTORY_BACKEND", "json")
    if isinstance(backend, str) and backend in HISTORY_BACKENDS:
        kls_history = HISTORY_BACKENDS[backend]
    elif xt.is_class(backend):
        kls_history = backend
    elif isinstance(backend, History):
        return backend
    else:
        print(
            f"Unknown history backend: {backend}. Using JSON version",
            file=sys.stderr,
        )
        kls_history = JsonHistory

    try:
        return kls_history(**kwargs)
    except Exception as e:
        xt.print_exception(
            f"Error during load {kls_history}: {e}\n"
            f"Set $XONSH_HISTORY_BACKEND='dummy' to disable history.\n"
            f"History disabled."
        )
        return DummyHistory()
