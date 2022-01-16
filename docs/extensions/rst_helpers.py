"""ReST-Jinja2 helpers"""
import re


def underline_title(title: str, level: int = -1):
    symbols = "-.^"
    if level < len(symbols):
        under = symbols[level]
    else:
        under = symbols[-1]
    return under * len(title)


def to_valid_id(name: str) -> str:
    return re.sub(r"[^\w]", "_", name.lower()).strip("_")


def to_valid_name(name: str) -> str:
    return name.replace("`", "")


def indent_depth(depth: int = None):
    return " " * ((1 if depth else 0) * 4)


def to_ref_string(title: str, underline=False, depth=-1) -> str:
    title = str(title)
    ref = f":ref:`{to_valid_name(title)} <{to_valid_id(title)}>`"
    if underline:
        return "\n".join([ref, underline_title(ref, depth)])
    return ref


def iterator_for_divmod(iterable, div: int = 3):
    items = list(iterable)
    size = len(items)
    rem = size % div
    complement = size + div - rem
    for i in range(complement):
        if i < size:
            yield items[i]
        else:
            yield None
