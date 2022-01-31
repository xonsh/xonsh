"""CWD related prompt formatter"""

import os
import shutil

import xonsh.platform as xp
import xonsh.tools as xt
from xonsh.built_ins import XSH


def _replace_home(x: str):
    home = os.path.expanduser("~")
    if x.startswith(home):
        x = x.replace(home, "~", 1)

    if xp.ON_WINDOWS:
        if XSH.env.get("FORCE_POSIX_PATHS") and os.altsep:
            x = x.replace(os.sep, os.altsep)

    return x


def _replace_home_cwd():
    pwd = XSH.env["PWD"].replace("{", "{{").replace("}", "}}")
    return _replace_home(pwd)


def _collapsed_pwd():
    sep = xt.get_sep()
    pwd = _replace_home_cwd().split(sep)
    size = len(pwd)
    leader = sep if size > 0 and len(pwd[0]) == 0 else ""
    base = [
        i[0] if ix != size - 1 and i[0] != "." else i[0:2] if ix != size - 1 else i
        for ix, i in enumerate(pwd)
        if len(i) > 0
    ]
    return leader + sep.join(base)


def _dynamically_collapsed_pwd():
    """Return the compact current working directory.  It respects the
    environment variable DYNAMIC_CWD_WIDTH.
    """
    original_path = _replace_home_cwd()
    target_width, units = XSH.env["DYNAMIC_CWD_WIDTH"]
    elision_char = XSH.env["DYNAMIC_CWD_ELISION_CHAR"]
    if target_width == float("inf"):
        return original_path
    if units == "%":
        cols, _ = shutil.get_terminal_size()
        target_width = (cols * target_width) // 100
    sep = xt.get_sep()
    pwd = original_path.split(sep)
    last = pwd.pop()
    remaining_space = target_width - len(last)
    # Reserve space for separators
    remaining_space_for_text = remaining_space - len(pwd)
    parts = []
    for i in range(len(pwd)):
        part = pwd[i]
        part_len = int(
            min(len(part), max(1, remaining_space_for_text // (len(pwd) - i)))
        )
        remaining_space_for_text -= part_len
        if len(part) > part_len:
            reduced_part = part[0 : part_len - len(elision_char)] + elision_char
            parts.append(reduced_part)
        else:
            parts.append(part)
    parts.append(last)
    full = sep.join(parts)
    truncature_char = elision_char if elision_char else "..."
    # If even if displaying one letter per dir we are too long
    if len(full) > target_width:
        # We truncate the left most part
        full = truncature_char + full[int(-target_width) + len(truncature_char) :]
        # if there is not even a single separator we still
        # want to display at least the beginning of the directory
        if full.find(sep) == -1:
            full = (truncature_char + sep + last)[
                0 : int(target_width) - len(truncature_char)
            ] + truncature_char
    return full
