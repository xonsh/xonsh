import builtins


def get_filter_function():
    csc = builtins.__xonsh_env__.get('CASE_SENSITIVE_COMPLETIONS')
    if csc:
        def filt(s, x): return s.startswith(x)
    else:
        def filt(s, x): return s.lower().startswith(x.lower())
    return filt


def is_iterable(x):
    try:
        _ = iter(x)
        return True
    except:
        return False


def justify(s, max_length, left_pad=0):
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
