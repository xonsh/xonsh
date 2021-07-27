"""
Import statement completions.
Contains modified code from the IPython project (at core/completerlib.py).

# Copyright (c) IPython Development Team.
# Distributed under the terms of the Modified BSD License.
"""

import os
import re
import sys
import glob
import inspect
from time import time
from importlib import import_module
from importlib.machinery import all_suffixes
from zipimport import zipimporter
import typing as tp

from xonsh.built_ins import XSH
from xonsh.lazyasd import lazyobject
from xonsh.completers.tools import (
    CompleterResult,
    contextual_completer,
    get_filter_function,
    RichCompletion,
)
from xonsh.parsers.completion_context import CompletionContext

_suffixes = all_suffixes()

# Time in seconds after which we give up
TIMEOUT_GIVEUP = 2


@lazyobject
def IMPORT_RE():
    # Regular expression for the python import statement
    return re.compile(r'(?P<name>[^\W\d]\w*?)'
                      r'(?P<package>[/\\]__init__)?'
                      r'(?P<suffix>%s)$' %
                      r'|'.join(re.escape(s) for s in _suffixes))


def module_list(path):
    """
    Return the list containing the names of the modules available in the given
    folder.
    """
    # sys.path has the cwd as an empty string, but isdir/listdir need it as '.'
    if path == '':
        path = '.'

    # A few local constants to be used in loops below
    pjoin = os.path.join

    if os.path.isdir(path):
        # Build a list of all files in the directory and all files
        # in its subdirectories. For performance reasons, do not
        # recurse more than one level into subdirectories.
        files = []
        for root, dirs, nondirs in os.walk(path, followlinks=True):
            subdir = root[len(path)+1:]
            if subdir:
                files.extend(pjoin(subdir, f) for f in nondirs)
                dirs[:] = [] # Do not recurse into additional subdirectories.
            else:
                files.extend(nondirs)

    else:
        try:
            files = list(zipimporter(path)._files.keys())
        except:
            files = []

    # Build a list of modules which match the import_re regex.
    modules = []
    for f in files:
        m = IMPORT_RE.match(f)
        if m:
            modules.append(m.group('name'))
    return list(set(modules))


def get_root_modules():
    """
    Returns a list containing the names of all the modules available in the
    folders of the pythonpath.
    """
    rootmodules_cache = XSH.modules_cache
    rootmodules = list(sys.builtin_module_names)
    start_time = time()
    store = False
    for path in sys.path:
        try:
            modules = rootmodules_cache[path]
        except KeyError:
            modules = module_list(path)
            try:
                modules.remove('__init__')
            except ValueError:
                pass
            if path not in ('', '.'): # cwd modules should not be cached
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
        return not(attr[:2] == '__' and attr[-2:] == '__')


def try_import(mod: str, only_modules=False) -> tp.List[str]:
    """
    Try to import given module and return list of potential completions.
    """
    mod = mod.rstrip('.')
    try:
        m = import_module(mod)
    except:
        return []

    m_is_init = '__init__' in (getattr(m, '__file__', '') or '')

    completions = []
    if (not hasattr(m, '__file__')) or (not only_modules) or m_is_init:
        completions.extend( [attr for attr in dir(m) if
                             is_importable(m, attr, only_modules)])

    completions.extend(getattr(m, '__all__', []))
    if m_is_init:
        completions.extend(module_list(os.path.dirname(m.__file__)))
    completions_set = {c for c in completions if isinstance(c, str)}
    completions_set.discard('__init__')
    return list(completions_set)
