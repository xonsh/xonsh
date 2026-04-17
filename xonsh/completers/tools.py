"""Xonsh completer tools."""

import inspect
import os
import shlex
import subprocess
import textwrap
import typing as tp
from functools import wraps

import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.lib.lazyasd import lazyobject
from xonsh.parsers.completion_context import CommandContext, CompletionContext


def _filter_with_func(text, prefix, func):
    if isinstance(text, RichCompletion) and text.display:
        parts = [p.strip() for p in text.display.split(",")]
        return any(map(lambda part: func(part.strip(), prefix), parts))
    return func(text, prefix)


def _filter_substring(text, prefix):
    func = lambda txt, pre: pre.lower() in txt.lower()
    return _filter_with_func(text, prefix, func)


def _filter_prefix(text, prefix):
    func = lambda txt, pre: txt.lower().startswith(pre.lower())
    return _filter_with_func(text, prefix, func)


def get_filter_function():
    """Return the completion filter function based on ``$XONSH_COMPLETER_MODE``.

    Modes:

    * ``"substring_tier"`` (default) — completions are filtered by
      case-insensitive substring match.  The pipeline's tier-based sort
      ranks prefix matches above substring matches.
    * ``"prefix"`` — only completions that start with the prefix are
      shown (case-insensitive).
    """
    from xonsh.built_ins import XSH

    mode = (XSH.env or {}).get("XONSH_COMPLETER_MODE", "substring_tier")
    if mode == "prefix":
        return _filter_prefix
    return _filter_substring


def justify(s, max_length, left_pad=0):
    """
    Re-wrap the string s so that each line is no more than max_length
    characters long, padding all lines but the first on the left with the
    string left_pad.
    """
    txt = textwrap.wrap(s, width=max_length, subsequent_indent=" " * left_pad)
    return "\n".join(txt)


class RichCompletion(str):
    """A rich completion that completers can return instead of a string"""

    def __new__(cls, value, *args, **kwargs):
        completion = super().__new__(cls, value)
        # ``str``'s ``__new__`` doesn't call ``__init__``, so we'll call it ourselves
        cls.__init__(completion, value, *args, **kwargs)
        return completion

    def __init__(
        self,
        value: str,
        prefix_len: int | None = None,
        display: str | None = None,
        description: str = "",
        style: str = "",
        append_closing_quote: bool = True,
        append_space: bool = False,
        provider: str | None = None,
    ):
        """
        Parameters
        ----------
        value :
            The completion's actual value.
        prefix_len :
            Length of the prefix to be replaced in the completion.
            If None, the default prefix len will be used.
        display :
            Text to display in completion option list instead of ``value``.
            NOTE: If supplied, the common prefix with other completions won't be removed.
        description :
            Extra text to display when the completion is selected.
        style :
            Style to pass to prompt-toolkit's ``Completion`` object.
        append_closing_quote :
            Whether to append a closing quote to the completion if the cursor is after it.
            See ``Completer.complete`` in ``xonsh/completer.py``
        append_space :
            Whether to append a space after the completion.
            This is intended to work with ``appending_closing_quote``, so the space will be added correctly **after** the closing quote.
            This is used in ``Completer.complete``.
            An extra bonus is that the space won't show up in the ``display`` attribute.
        provider :
            Optional, debug-only tag identifying the sub-source inside the
            completer that produced this completion (e.g. ``"alias"``,
            ``"command"``, ``"python"``, ``"path"``). Surfaced by
            ``$XONSH_COMPLETER_TRACE`` so users can tell whether a match
            came from, say, an alias vs. a ``$PATH`` executable inside the
            same ``base`` completer. Does not affect UX.
        """
        super().__init__()
        self.prefix_len = prefix_len
        self.display = display
        self.description = description
        self.style = style
        self.append_closing_quote = append_closing_quote
        self.append_space = append_space
        self.provider = provider

    @property
    def value(self):
        return str(self)

    def __repr__(self):
        # don't print default values
        attrs = ", ".join(
            f"{name}={getattr(self, name)!r}"
            for name, default in RICH_COMPLETION_DEFAULTS
            if getattr(self, name) != default
        )
        return f"RichCompletion({self.value!r}, {attrs})"

    def replace(self, **kwargs):
        """Create a new RichCompletion with replaced attributes"""
        default_kwargs = dict(
            value=self.value,
            **self.__dict__,
        )
        default_kwargs.update(kwargs)
        return RichCompletion(**default_kwargs)


@lazyobject
def RICH_COMPLETION_DEFAULTS():
    """The ``__init__`` parameters' default values (excluding ``self`` and ``value``)."""
    return [
        (name, param.default)
        for name, param in inspect.signature(RichCompletion.__init__).parameters.items()
        if name not in ("self", "value")
    ]


Completion = tp.Union[RichCompletion, str]  # noqa: UP007
CompleterResult = tp.Union[set[Completion], tuple[set[Completion], int], None]  # noqa: UP007
ContextualCompleter = tp.Callable[[CompletionContext], CompleterResult]


def contextual_completer(func: ContextualCompleter):
    """Decorator for a contextual completer

    This is used to mark completers that want to use the parsed completion context.
    See ``xonsh/parsers/completion_context.py``.

    ``func`` receives a single CompletionContext object.
    """
    func.contextual = True  # type: ignore
    return func


def is_contextual_completer(func):
    return getattr(func, "contextual", False)


def contextual_command_completer(func: tp.Callable[[CommandContext], CompleterResult]):
    """like ``contextual_completer``,
    but will only run when completing a command and will directly receive the ``CommandContext`` object
    """

    @contextual_completer
    @wraps(func)
    def _completer(context: CompletionContext) -> CompleterResult:
        if context.command is not None:
            return func(context.command)
        return None

    return _completer


def contextual_command_completer_for(cmd: str):
    """like ``contextual_command_completer``,
    but will only run when completing the ``cmd`` command"""

    def decor(func: tp.Callable[[CommandContext], CompleterResult]):
        @contextual_completer
        @wraps(func)
        def _completer(context: CompletionContext) -> CompleterResult:
            if context.command is not None and context.command.completing_command(cmd):
                return func(context.command)
            return None

        return _completer

    return decor


def non_exclusive_completer(func):
    """Decorator for a non-exclusive completer

    This is used to mark completers that will be collected with other completer's results.
    """
    func.non_exclusive = True  # type: ignore
    return func


def is_exclusive_completer(func):
    return not getattr(func, "non_exclusive", False)


def apply_lprefix(comps, lprefix):
    if lprefix is None:
        return comps

    for comp in comps:
        if isinstance(comp, RichCompletion):
            if comp.prefix_len is None:
                yield comp.replace(prefix_len=lprefix)
            else:
                # this comp has a custom prefix len
                yield comp
        else:
            yield RichCompletion(comp, prefix_len=lprefix)


def _tag_each(comps, provider: str):
    """Yield completions with ``provider`` set, promoting ``str`` to
    ``RichCompletion``. A completion that already has a ``provider`` keeps
    its own — lets a nested completer override the outer tag.
    """
    for comp in comps:
        if isinstance(comp, RichCompletion):
            if comp.provider is None:
                yield comp.replace(provider=provider)
            else:
                yield comp
        else:
            yield RichCompletion(comp, provider=provider)


def tag_provider(result, provider: str):
    """Tag completer output with ``provider`` for ``$XONSH_COMPLETER_TRACE``.

    Accepts any of the three standard completer return shapes and
    preserves the shape so downstream pipeline logic (exclusivity,
    filtering, lprefix) is unaffected:

    - ``None`` → returned unchanged.
    - ``(comps, extra)`` 2-tuple → ``(tagged_generator, extra)``.
    - Any other iterable → generator of tagged completions.
    """
    if result is None:
        return None
    if isinstance(result, tuple) and len(result) == 2:
        comps, extra = result
        return _tag_each(comps, provider), extra
    return _tag_each(result, provider)


def completion_from_cmd_output(line: str, append_space=False):
    line = line.strip()
    if "\t" in line:
        cmd, desc = map(str.strip, line.split("\t", maxsplit=1))
    else:
        cmd, desc = line, ""

    # special treatment for path completions.
    # not appending space even if it is a single candidate.
    if cmd.endswith(os.sep) or (os.altsep and cmd.endswith(os.altsep)):
        append_space = False

    return RichCompletion(
        cmd,
        description=desc,
        append_space=append_space,
    )


def sub_proc_get_output(*args, **env_vars: str) -> "tuple[bytes, bool]":
    env = {}

    # env.detype is mutable, so update the newly created variable
    env.update(XSH.env.detype())

    env.update(env_vars)  # prefer passed env variables

    out = b""
    not_found = False
    try:
        out = subprocess.run(
            args,
            env=env,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
        ).stdout
    except FileNotFoundError:
        not_found = True
    except Exception as ex:
        xt.print_exception(f"Failed to get completions from sub-proc: {args} ({ex!r})")

    return out, not_found


def complete_from_sub_proc(*args: str, sep=None, filter_prefix=None, **env_vars: str):
    if sep is None:
        sep = str.splitlines
    filter_func = get_filter_function()
    stdout, _ = sub_proc_get_output(*args, **env_vars)

    if stdout:
        output = stdout.decode().strip()
        if callable(sep):
            lines = sep(output)
        else:
            lines = output.split(sep)

        # Drop blank lines before counting / yielding so that a subprocess
        # emitting trailing/extra whitespace doesn't produce empty
        # RichCompletion objects (see #5810).
        lines = [ln for ln in lines if ln.strip()]

        # if there is a single completion candidate then maybe it is over
        append_space = len(lines) == 1 and not lines[0].rstrip().endswith(os.sep)
        for line in lines:
            if filter_prefix and (not filter_func(line, filter_prefix)):
                continue
            comp = completion_from_cmd_output(line, append_space)
            yield comp


def _shlex_split_safe(s):
    """Split like shlex but preserve backslashes on Windows.

    ``shlex.split`` in POSIX mode treats ``\\`` as an escape character,
    which corrupts Windows paths (``".\\dir"`` → ``".dir"``).  Using
    ``posix=False`` keeps backslashes intact.
    """
    lex = shlex.shlex(s, posix=False)
    lex.whitespace_split = True
    return list(lex)


def comp_based_completer(ctx: CommandContext, start_index=0, **env: str):
    """Helper function to complete commands such as ``pip``,``django-admin``,... that use bash's ``complete``"""
    prefix = ctx.prefix

    args = [arg.value for arg in ctx.args]
    if prefix:
        args.append(prefix)

    yield from complete_from_sub_proc(
        *args[: start_index + 1],
        sep=_shlex_split_safe,
        COMP_WORDS=os.linesep.join(args[start_index:]) + os.linesep,
        COMP_CWORD=str(ctx.arg_index - start_index),
        **env,
    )
