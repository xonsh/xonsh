"""
Import statement completions.
Contains modified code from the IPython project (at core/completerlib.py).

# Copyright (c) IPython Development Team.
# Distributed under the terms of the Modified BSD License.
"""

import inspect
import os
import re
import sys
from importlib import import_module
from importlib.machinery import all_suffixes
from time import time
from zipimport import zipimporter

from xonsh.built_ins import XSH
from xonsh.completers.tools import (
    RichCompletion,
    contextual_completer,
    get_filter_function,
)
from xonsh.lib.lazyasd import lazyobject
from xonsh.parsers.completion_context import CompletionContext

_suffixes = all_suffixes()

# Time in seconds after which we give up
TIMEOUT_GIVEUP = 2


@lazyobject
def IMPORT_RE():
    # Regular expression for the python import statement
    suffixes = r"|".join(re.escape(s) for s in _suffixes)
    return re.compile(
        r"(?P<name>[^\W\d]\w*?)"
        r"(?P<package>[/\\]__init__)?"
        rf"(?P<suffix>{suffixes})$"
    )


def module_list(path):
    """
    Return the list containing the names of the modules available in the given
    folder.
    """
    # sys.path has the cwd as an empty string, but isdir/listdir need it as '.'
    if path == "":
        path = "."

    # A few local constants to be used in loops below
    pjoin = os.path.join

    if os.path.isdir(path):
        # Build a list of all files in the directory and all files
        # in its subdirectories. For performance reasons, do not
        # recurse more than one level into subdirectories.
        files = []
        for root, dirs, nondirs in os.walk(path, followlinks=True):
            subdir = root[len(path) + 1 :]
            if subdir:
                files.extend(pjoin(subdir, f) for f in nondirs)
                dirs[:] = []  # Do not recurse into additional subdirectories.
            else:
                files.extend(nondirs)

    else:
        try:
            files = list(zipimporter(path)._files.keys())
        except:  # noqa
            files = []

    # Build a list of modules which match the import_re regex.
    modules = []
    for f in files:
        m = IMPORT_RE.match(f)
        if m:
            modules.append(m.group("name"))
    return list(set(modules))


def get_root_modules():
    """
    Returns a list containing the names of all the modules available in the
    folders of the pythonpath.
    """
    rootmodules_cache = XSH.modules_cache
    rootmodules = list(sys.builtin_module_names)
    start_time = time()
    for path in sys.path:
        try:
            modules = rootmodules_cache[path]
        except KeyError:
            modules = module_list(path)
            try:
                modules.remove("__init__")
            except ValueError:
                pass
            if path not in ("", "."):  # cwd modules should not be cached
                rootmodules_cache[path] = modules
            if time() - start_time > TIMEOUT_GIVEUP:
                print("\nwarning: Getting root modules is taking too long, we give up")
                return []
        rootmodules.extend(modules)
    rootmodules = list(set(rootmodules))
    return rootmodules


def is_importable(module, attr, only_modules):
    if only_modules:
        return inspect.ismodule(getattr(module, attr))
    else:
        return not (attr[:2] == "__" and attr[-2:] == "__")


def is_possible_submodule(module, attr):
    try:
        obj = getattr(module, attr)
    except AttributeError:
        # Is possilby an unimported submodule
        return True
    except TypeError:
        # https://github.com/ipython/ipython/issues/9678
        return False
    return inspect.ismodule(obj)


def try_import(mod: str, only_modules=False) -> list[str]:
    """
    Try to import given module and return list of potential completions.
    """
    mod = mod.rstrip(".")
    try:
        m = import_module(mod)
    except Exception:
        return []

    m_is_init = "__init__" in (getattr(m, "__file__", "") or "")

    completions = []
    if (not hasattr(m, "__file__")) or (not only_modules) or m_is_init:
        completions.extend(
            [attr for attr in dir(m) if is_importable(m, attr, only_modules)]
        )

    m_all = getattr(m, "__all__", [])
    if only_modules:
        completions.extend(attr for attr in m_all if is_possible_submodule(m, attr))
    else:
        completions.extend(m_all)

    if m_is_init:
        if m.__file__:
            completions.extend(module_list(os.path.dirname(m.__file__)))
    completions_set = {c for c in completions if isinstance(c, str)}
    completions_set.discard("__init__")
    return list(completions_set)


###############
# Xonsh code: #
###############


def filter_completions(prefix, completions):
    filt = get_filter_function()
    for comp in completions:
        if filt(comp, prefix):
            yield comp


@contextual_completer
def complete_import(context: CompletionContext):
    """
    Completes module names and objects for "import ..." and "from ... import
    ...".
    """
    if not (context.command and context.python):
        # Imports are only possible in independent lines (not in `$()` or `@()`).
        # This means it's python code, but also can be a command as far as the parser is concerned.
        return None

    command = context.command

    if command.opening_quote:
        # can't have a quoted import
        return None

    arg_index = command.arg_index
    prefix = command.prefix
    args = command.args

    if arg_index == 1 and args[0].value == "from":
        # completing module to import
        return complete_module(prefix)
    if arg_index >= 1 and args[0].value == "import":
        # completing module to import, might be multiple modules
        prefix = prefix.rsplit(",", 1)[-1]
        return complete_module(prefix), len(prefix)
    if arg_index == 2 and args[0].value == "from":
        return {RichCompletion("import", append_space=True)}
    if arg_index > 2 and args[0].value == "from" and args[2].value == "import":
        # complete thing inside a module, might be multiple objects
        module = args[1].value
        prefix = prefix.rsplit(",", 1)[-1]
        return filter_completions(prefix, try_import(module)), len(prefix)
    return set()


def complete_module(prefix):
    if not prefix:
        modules = get_root_modules()
    else:
        mod = prefix.split(".")
        if len(mod) < 2:
            modules = get_root_modules()
        else:
            completion_list = try_import(".".join(mod[:-1]), only_modules=True)
            modules = (".".join(mod[:-1] + [el]) for el in completion_list)

    yield from filter_completions(prefix, modules)
