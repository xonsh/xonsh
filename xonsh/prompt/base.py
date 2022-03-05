"""Base prompt, provides PROMPT_FIELDS and prompt related functions"""

import collections.abc as cabc
import itertools
import os
import re
import socket
import sys
import typing as tp

import xonsh.lazyasd as xl
import xonsh.platform as xp
import xonsh.tools as xt
from xonsh.built_ins import XSH
from xonsh.completers.commands import ModuleMatcher

if tp.TYPE_CHECKING:
    from xonsh.built_ins import XonshSession


@xt.lazyobject
def DEFAULT_PROMPT():
    return default_prompt()


class _ParsedToken(tp.NamedTuple):
    """It can either be a literal value alone or a field and its resultant value"""

    value: str
    field: tp.Optional[str] = None


class ParsedTokens(tp.NamedTuple):
    tokens: tp.List[_ParsedToken]
    template: tp.Union[str, tp.Callable]

    def process(self) -> str:
        """Wrapper that gets formatter-function from environment and returns final prompt."""
        processor = XSH.env.get(  # type: ignore
            "PROMPT_TOKENS_FORMATTER", prompt_tokens_formatter_default
        )
        return processor(self)

    def update(
        self,
        idx: int,
        val: tp.Optional[str],
        spec: tp.Optional[str],
        conv: tp.Optional[str],
    ) -> None:
        """Update tokens list in-place"""
        if idx < len(self.tokens):
            tok = self.tokens[idx]
            self.tokens[idx] = _ParsedToken(_format_value(val, spec, conv), tok.field)


def prompt_tokens_formatter_default(container: ParsedTokens) -> str:
    """
        Join the tokens

    Parameters
    ----------
    container: ParsedTokens
        parsed tokens holder

    Returns
    -------
    str
        process the tokens and finally return the prompt string
    """
    return "".join([tok.value for tok in container.tokens])


class PromptFormatter:
    """Class that holds all the related prompt formatting methods,
    uses the ``PROMPT_FIELDS`` envvar (no color formatting).
    """

    def __init__(self):
        self.cache = {}

    def __call__(self, template=DEFAULT_PROMPT, fields=None, **kwargs) -> str:
        """Formats a xonsh prompt template string."""

        # keep cache only during building prompt
        self.cache.clear()

        if fields is None:
            self.fields = XSH.env.get("PROMPT_FIELDS", PROMPT_FIELDS)  # type: ignore
        else:
            self.fields = fields
        try:
            toks = self._format_prompt(template=template, **kwargs)
            prompt = toks.process()
        except Exception as ex:
            # make it obvious why it has failed
            print(
                f"Failed to format prompt `{template}`-> {type(ex)}:{ex}",
                file=sys.stderr,
            )
            return _failover_template_format(template)
        return prompt

    def _format_prompt(self, template=DEFAULT_PROMPT, **kwargs) -> ParsedTokens:
        tmpl = template() if callable(template) else template
        toks = []
        for literal, field, spec, conv in xt.FORMATTER.parse(tmpl):
            if literal:
                toks.append(_ParsedToken(literal))
            entry = self._format_field(field, spec, conv, idx=len(toks), **kwargs)
            if entry is not None:
                toks.append(_ParsedToken(entry, field))

        return ParsedTokens(toks, template)

    def _format_field(self, field, spec="", conv=None, **kwargs):
        if field is None:
            return
        elif field.startswith("$"):
            val = XSH.env[field[1:]]
            return _format_value(val, spec, conv)
        elif field in self.fields:
            val = self._get_field_value(field, spec=spec, conv=conv, **kwargs)
            return _format_value(val, spec, conv)
        else:
            # color or unknown field, return as is
            return "{" + field + "}"

    def _get_field_value(self, field, **kwargs):
        field_value = self.fields[field]
        if field_value in self.cache:
            return self.cache[field_value]
        return self._no_cache_field_value(field, field_value, **kwargs)

    def _no_cache_field_value(self, field, field_value, **_):
        try:
            value = field_value() if callable(field_value) else field_value
            self.cache[field_value] = value
        except Exception:
            print("prompt: error: on field {!r}" "".format(field), file=sys.stderr)
            xt.print_exception()
            value = f"{{BACKGROUND_RED}}{{ERROR:{field}}}{{RESET}}"
        return value


@xl.lazyobject
def PROMPT_FIELDS():
    return PromptFields()


def default_prompt():
    """Creates a new instance of the default prompt."""
    if xp.ON_CYGWIN or xp.ON_MSYS:
        dp = (
            "{env_name}"
            "{BOLD_GREEN}{user}@{hostname}"
            "{BOLD_BLUE} {cwd} {prompt_end}{RESET} "
        )
    elif xp.ON_WINDOWS and not xp.win_ansi_support():
        dp = (
            "{env_name}"
            "{BOLD_INTENSE_GREEN}{user}@{hostname}{BOLD_INTENSE_CYAN} "
            "{cwd}{branch_color}{curr_branch: {}}{RESET} "
            "{BOLD_INTENSE_CYAN}{prompt_end}{RESET} "
        )
    else:
        dp = (
            "{env_name}"
            "{BOLD_GREEN}{user}@{hostname}{BOLD_BLUE} "
            "{cwd}{branch_color}{curr_branch: {}}{RESET} "
            "{BOLD_BLUE}{prompt_end}{RESET} "
        )
    return dp


def _failover_template_format(template):
    if callable(template):
        try:
            # Exceptions raises from function of producing $PROMPT
            # in user's xonshrc should not crash xonsh
            return template()
        except Exception:
            xt.print_exception()
            return "$ "
    return template


@xt.lazyobject
def RE_HIDDEN():
    return re.compile("\001.*?\002")


def multiline_prompt(curr=""):
    """Returns the filler text for the prompt in multiline scenarios."""
    line = curr.rsplit("\n", 1)[1] if "\n" in curr else curr
    line = RE_HIDDEN.sub("", line)  # gets rid of colors
    # most prompts end in whitespace, head is the part before that.
    head = line.rstrip()
    headlen = len(head)
    # tail is the trailing whitespace
    tail = line if headlen == 0 else line.rsplit(head[-1], 1)[1]
    # now to construct the actual string
    dots = XSH.env.get("MULTILINE_PROMPT")
    dots = dots() if callable(dots) else dots
    if dots is None or len(dots) == 0:
        return ""
    tokstr = xt.format_color(dots, hide=True)
    baselen = 0
    basetoks = []
    for x in tokstr.split("\001"):
        pre, sep, post = x.partition("\002")
        if len(sep) == 0:
            basetoks.append(("", pre))
            baselen += len(pre)
        else:
            basetoks.append(("\001" + pre + "\002", post))
            baselen += len(post)
    if baselen == 0:
        return xt.format_color("{RESET}" + tail, hide=True)
    toks = basetoks * (headlen // baselen)
    n = headlen % baselen
    count = 0
    for tok in basetoks:
        slen = len(tok[1])
        newcount = slen + count
        if slen == 0:
            continue
        elif newcount <= n:
            toks.append(tok)
        else:
            toks.append((tok[0], tok[1][: n - count]))
        count = newcount
        if n <= count:
            break
    toks.append((xt.format_color("{RESET}", hide=True), tail))
    rtn = "".join(itertools.chain.from_iterable(toks))
    return rtn


def is_template_string(template, PROMPT_FIELDS=None):
    """Returns whether or not the string is a valid template."""
    template = template() if callable(template) else template
    try:
        included_names = {i[1] for i in xt.FORMATTER.parse(template)}
    except ValueError:
        return False
    included_names.discard(None)
    if PROMPT_FIELDS is None:
        fmtter = XSH.env.get("PROMPT_FIELDS", PROMPT_FIELDS)
    else:
        fmtter = PROMPT_FIELDS
    known_names = set(fmtter.keys())
    return included_names <= known_names


def _format_value(val, spec, conv) -> str:
    """Formats a value from a template string {val!conv:spec}. The spec is
    applied as a format string itself, but if the value is None, the result
    will be empty. The purpose of this is to allow optional parts in a
    prompt string. For example, if the prompt contains '{current_job:{} | }',
    and 'current_job' returns 'sleep', the result is 'sleep | ', and if
    'current_job' returns None, the result is ''.
    """
    if val is None:
        return ""
    val = xt.FORMATTER.convert_field(val, conv)
    if spec:
        val = xt.FORMATTER.format(spec, val)
    if not isinstance(val, str):
        val = str(val)
    return val


class PromptFields(cabc.MutableMapping):
    def __init__(self):
        self._items = {}

        self._cache = {}
        """for callbacks this will catch the value and should be cleared between prompts"""

        self._matcher = ModuleMatcher(
            "xonsh.prompt",
            *XSH.env.get("XONSH_PROMPT_NS", []),
        )

    def __getitem__(self, item):
        if item not in self._items:
            self._matcher.get_module()
        return self._items[item]

    def load_initial(self):
        # todo: use module matcher to load these on demand
        from xonsh.prompt.cwd import (
            _collapsed_pwd,
            _replace_home_cwd,
            _dynamically_collapsed_pwd,
        )
        from xonsh.prompt.job import _current_job
        from xonsh.prompt.env import env_name, vte_new_tab_cwd
        from xonsh.prompt.vc import current_branch, branch_color, branch_bg_color
        from xonsh.prompt import gitstatus
        from xonsh.prompt.times import _localtime

        fields = PromptFields(
            dict(
                user=xp.os_environ.get(
                    "USERNAME" if xp.ON_WINDOWS else "USER", "<user>"
                ),
                prompt_end="#" if xt.is_superuser() else "$",
                hostname=socket.gethostname().split(".", 1)[0],
                cwd=_dynamically_collapsed_pwd,
                cwd_dir=lambda: os.path.join(os.path.dirname(_replace_home_cwd()), ""),
                cwd_base=lambda: os.path.basename(_replace_home_cwd()),
                short_cwd=_collapsed_pwd,
                curr_branch=current_branch,
                branch_color=branch_color,
                branch_bg_color=branch_bg_color,
                current_job=_current_job,
                env_name=env_name,
                env_prefix="(",
                env_postfix=") ",
                vte_new_tab_cwd=vte_new_tab_cwd,
                gitstatus=gitstatus.gitstatus_prompt,
                time_format="%H:%M:%S",
                localtime=_localtime,
            )
        )

        # add gitstatus_* fields
        for fld in gitstatus._DEFS:
            if fld in {gitstatus._DEFS.HASH_INDICATOR, gitstatus._DEFS.SEPARATOR}:
                continue
            name = f"gitstatus_{fld.name.lower()}"
            fields[name] = getattr(gitstatus, name)

        return fields

    def get(self, key: "str|tp.Type[PromptField]") -> "str|PromptField":
        # todo: implement getting the instance i.e. the result if callable
        #   also cache values per prompt
        return


class LazyField:
    # these three fields will get updated by the caller
    prefix = ""
    suffix = ""
    value = ""

    updator = ""
    """module path to the function to load value on-demand"""

    join = ""
    """in case this combines values from other prompt fields"""

    fields: "tp.Tuple[str|tp.Type[LazyField], ...]" = ()
    """in case of combining values from other fields, list them here"""

    def __init__(self, ctx: "tp.Dict[str, tp.Any]", xsh: "XonshSession"):
        self.ctx = ctx
        self.xsh = xsh
        self.container = xsh.env["PROMPT_FIELDS"]

    def update(self):
        if self.fields:
            return self.join.join(self.gets(*self.fields))

        return self.value

    def __bool__(self):
        return bool(self.value)

    def __str__(self):
        return format(self)

    def __format__(self, format_spec: str):
        val = self.get_value()
        if val is None:
            # null value will return empty string
            return ""
        return self.prefix + format(val, format_spec) + self.suffix

    def get(self, fld, default=None):
        return self.container.get(fld, default=default)

    def gets(self, *flds):
        for fld in flds:
            val = self.get(fld)
            if val:
                yield format(val)
