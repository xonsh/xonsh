import builtins


def _filter_normal(s, x):
    return s.startswith(x)


def _filter_ignorecase(s, x):
    return s.lower().startswith(x.lower())


def get_filter_function():
    """
    Return an appropriate filtering function for completions, given the valid
    of $CASE_SENSITIVE_COMPLETIONS
    """
    csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
    if csc:
        return _filter_normal
    else:
        return _filter_ignorecase


def justify(s, max_length, left_pad=0):
    """
    Re-wrap the string s so that each line is no more than max_length
    characters long, padding all lines but the first on the left with the
    string left_pad.
    """
    toks = s.strip().split()
    lines = [[]]
    for tok in toks:
        new_length = (sum(len(i) for i in lines[-1]) +
                      len(lines[-1]) - 1 +
                      len(tok) +
                      left_pad)
        if new_length > max_length:
            lines.append([])
        lines[-1].append(tok)
    return "\n".join((((" " * left_pad) if ix != 0 else '') + " ".join(i))
                     for ix, i in enumerate(lines))
