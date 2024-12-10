def check_bad_str_token(tok):
    """Checks if a token is a bad string."""
    if tok.type == "ERRORTOKEN" and tok.value == "EOF in multi-line string":
        return True
    elif isinstance(tok.value, str) and not check_quotes(tok.value):
        return True
    else:
        return False


def check_quotes(s):
    """Checks a string to make sure that if it starts with quotes, it also
    ends with quotes.
    """
    from xonsh.tools import RE_BEGIN_STRING, RE_COMPLETE_STRING

    starts_as_str = RE_BEGIN_STRING.match(s) is not None
    ends_as_str = s.endswith('"') or s.endswith("'")
    if not starts_as_str and not ends_as_str:
        ok = True
    elif starts_as_str and not ends_as_str:
        ok = False
    elif not starts_as_str and ends_as_str:
        ok = False
    else:
        m = RE_COMPLETE_STRING.match(s)
        ok = m is not None
    return ok


def _offset_from_prev_lines(line, last):
    lines = line.splitlines(keepends=True)[:last]
    return sum(map(len, lines))


def _is_not_lparen_and_rparen(lparens, rtok):
    """Tests if an RPAREN token is matched with something other than a plain old
    LPAREN type.
    """
    # note that any([]) is False, so this covers len(lparens) == 0
    return rtok.type == "RPAREN" and any(x != "LPAREN" for x in lparens)
