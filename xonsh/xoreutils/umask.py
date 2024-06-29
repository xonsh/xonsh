"""Implements a umask command for xonsh."""

import os
import re

import xonsh.lib.lazyasd as xl


@xl.lazyobject
def symbolic_matcher():
    return re.compile(r"([ugo]*|a)([+-=])([^\s,]*)")


order = "rwx"
name_to_value = {"x": 1, "w": 2, "r": 4}
value_to_name = {v: k for k, v in name_to_value.items()}

class_to_loc = {"u": 6, "g": 3, "o": 0}  # how many bits to shift this class by
loc_to_class = {v: k for k, v in class_to_loc.items()}

function_map = {
    "+": lambda orig, new: orig | new,  # add the given permission
    "-": lambda orig, new: orig & ~new,  # remove the given permission
    "=": lambda orig, new: new,  # set the permissions exactly
}


def current_mask():
    out = os.umask(0)
    os.umask(out)
    return out


def invert(perms):
    return 0o777 - perms


def get_oct_digits(mode):
    """
    Separate a given integer into its three components
    """
    if not 0 <= mode <= 0o777:
        raise ValueError("expected a value between 000 and 777")
    return {"u": (mode & 0o700) >> 6, "g": (mode & 0o070) >> 3, "o": mode & 0o007}


def from_oct_digits(digits):
    o = 0
    for c, m in digits.items():
        o |= m << class_to_loc[c]
    return o


def get_symbolic_rep_single(digit):
    """
    Given a single octal digit, return the appropriate string representation.
    For example, 6 becomes "rw".
    """
    o = ""
    for sym in "rwx":
        num = name_to_value[sym]
        if digit & num:
            o += sym
            digit -= num
    return o


def get_symbolic_rep(number):
    digits = get_oct_digits(number)
    return ",".join(
        f"{class_}={get_symbolic_rep_single(digits[class_])}" for class_ in "ugo"
    )


def get_numeric_rep_single(rep):
    """
    Given a string representation, return the appropriate octal digit.
    For example, "rw" becomes 6.
    """
    o = 0
    for sym in set(rep):
        o += name_to_value[sym]
    return o


def single_symbolic_arg(arg, old=None):
    # we'll assume this always operates in the "forward" direction (on the
    # current permissions) rather than on the mask directly.
    if old is None:
        old = invert(current_mask())

    match = symbolic_matcher.match(arg)
    if not match:
        raise ValueError(f"could not parse argument {arg!r}")

    class_, op, mask = match.groups()

    if class_ == "a":
        class_ = "ugo"

    invalid_chars = [i for i in mask if i not in name_to_value]
    if invalid_chars:
        raise ValueError(f"invalid mask {mask!r}")

    digits = get_oct_digits(old)
    new_num = get_numeric_rep_single(mask)

    for c in set(class_):
        digits[c] = function_map[op](digits[c], new_num)

    return from_oct_digits(digits)


def valid_numeric_argument(x):
    try:
        return len(x) == 3 and all(0 <= int(i) <= 7 for i in x)
    except:
        return False


def umask(args, stdin, stdout, stderr):
    if "-h" in args:
        print(UMASK_HELP, file=stdout)
        return 0
    symbolic = False
    while "-S" in args:
        symbolic = True
        args.remove("-S")
    cur = current_mask()
    if len(args) == 0:
        # just print the current mask
        if symbolic:
            to_print = get_symbolic_rep(invert(cur))
        else:
            to_print = oct(cur)[2:]
            while len(to_print) < 3:
                to_print = f"0{to_print}"
        print(to_print, file=stdout)
        return 0
    else:
        num = [valid_numeric_argument(i) for i in args]
        if any(num):
            if not all(num):
                print("error: can't mix numeric and symbolic arguments", file=stderr)
                return 1
            if len(num) != 1:
                print("error: can't have more than one numeric argument", file=stderr)
                return 1
        for arg, isnum in zip(args, num):
            if isnum:
                cur = int(arg, 8)
            else:
                # this mode operates not on the mask, but on the current
                # _permissions_.  so invert first, operate, then invert back.
                cur = invert(cur)
                for subarg in arg.split(","):
                    try:
                        cur = single_symbolic_arg(subarg, cur)
                    except:
                        print(
                            f"error: could not parse argument: {subarg!r}", file=stderr
                        )
                        return 1
                cur = invert(cur)
            os.umask(cur)


UMASK_HELP = """Usage: umask [-S] [mode]...
View or set the file creation mask.

  -S             when printing, show output in symbolic format
  -h  --help     display this message and exit

This version of umask was written in Python for tako: https://takoshell.org
Based on the umask command from Bash:
https://www.gnu.org/software/bash/manual/html_node/Bourne-Shell-Builtins.html"""

if __name__ == "__main__":
    import sys

    umask(sys.argv, sys.stdin, sys.stdout, sys.stderr)
