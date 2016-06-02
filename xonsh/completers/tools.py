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
