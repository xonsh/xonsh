"""Inspect variables added in the interactive session with ``whos``."""

import reprlib
import weakref

from xonsh.events import events


class _Whos:
    def __init__(self, xsh):
        self.session = weakref.ref(xsh)
        self.baseline = frozenset()
        self.event = events.on_pre_cmdloop

        def capture(**kwargs):
            session = self.session()
            if session is not None:
                self.baseline = frozenset(
                    name for name in session.ctx if isinstance(name, str)
                )

        self.capture = capture
        self.event(capture)
        self.finalizer = weakref.finalize(xsh, self.event.discard, capture)

        @xsh.aliases.register("whos")
        def whos(args, stdout=None, stderr=None):
            """List variables added since the interactive baseline."""
            session = self.session()
            if session is None:
                return
            ctx = session.ctx
            names = sorted(
                name
                for name in ctx
                if isinstance(name, str) and name not in self.baseline
            )
            if not names:
                print("No new variables.", file=stdout)
                return
            print("Name\tType\tValue", file=stdout)
            for name in names:
                try:
                    value = ctx[name]
                    kind = _safe_text(type(value).__name__)
                    preview = _safe_text(reprlib.repr(value))
                except Exception:
                    kind = "?"
                    preview = "<display failed>"
                print(f"{_safe_text(name)}\t{kind}\t{preview}", file=stdout)

        self.alias = xsh.aliases["whos"]

    def close(self):
        self.finalizer()
        session = self.session()
        if session is not None and "whos" in session.aliases:
            if session.aliases["whos"] is self.alias:
                del session.aliases["whos"]


def _safe_text(text):
    """Escape terminal controls and bound the final displayed text."""
    escaped = "".join(
        char if char.isprintable() else ascii(char)[1:-1] for char in text[:80]
    )
    return escaped if len(escaped) <= 80 else escaped[:77] + "..."


def _load_xontrib_(xsh, **kwargs):
    if getattr(xsh, "_whos_state", None) is not None:
        return
    if "whos" not in xsh.aliases:
        xsh._whos_state = _Whos(xsh)


def _unload_xontrib_(xsh, **kwargs):
    state = getattr(xsh, "_whos_state", None)
    if state is not None:
        state.close()
        del xsh._whos_state
