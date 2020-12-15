"""
small functions to create argparser CLI from functions.
"""

import argparse as ap
import os
import typing as tp


def _get_func_doc(doc: str) -> str:
    lines = doc.splitlines()
    if "Parameters" in lines:
        idx = lines.index("Parameters")
        lines = lines[:idx]
    return os.linesep.join(lines)


def _from_index_of(container: tp.Sequence[str], key: str):
    if key in container:
        idx = container.index(key)
        if idx + 1 < len(container):
            return container[idx + 1 :]
    return []


def _get_param_doc(doc: str, param: str) -> str:
    lines = tuple(doc.splitlines())
    if "Parameters" not in lines:
        return ""

    par_doc = []
    for lin in _from_index_of(lines, param):
        if lin and not lin.startswith(" "):
            break
        par_doc.append(lin)
    return os.linesep.join(par_doc).strip()


def get_doc(func: tp.Callable, parameter: str = None):
    """Parse the function docstring and return its help content

    Parameters
    ----------
    func
        a callable object that holds docstring
    parameter
        name of the function parameter to parse doc for

    Returns
    -------
    str
        doc of the parameter/function
    """
    import inspect

    doc = inspect.getdoc(func) or ""
    if parameter:
        return _get_param_doc(doc, parameter)
    else:
        return _get_func_doc(doc)


_FUNC_NAME = "_func_"


def make_parser(
    func: tp.Callable,
    subparser: ap._SubParsersAction = None,
    params: tp.Dict[str, tp.Dict[str, tp.Any]] = None,
    **kwargs
) -> "ap.ArgumentParser":
    """A bare-bones argparse builder from functions"""

    doc = get_doc(func)
    kwargs.setdefault("formatter_class", ap.RawTextHelpFormatter)
    if subparser is None:
        kwargs.setdefault("description", doc)
        parser = ap.ArgumentParser(**kwargs)
        parser.set_defaults(
            **{_FUNC_NAME: lambda stdout: parser.print_help(file=stdout)}
        )
        return parser
    else:
        parser = subparser.add_parser(
            kwargs.pop("prog", func.__name__),
            help=doc,
            **kwargs,
        )
        parser.set_defaults(**{_FUNC_NAME: func})

        if params:
            for par, args in params.items():
                args.setdefault("help", get_doc(func, par))
                parser.add_argument(par, **args)

        return parser


def dispatch(**ns):
    """call the sub-command selected by user"""
    import inspect

    func = ns[_FUNC_NAME]
    sign = inspect.signature(func)
    kwargs = {}
    for name, param in sign.parameters.items():
        kwargs[name] = ns[name]
    return func(**kwargs)
