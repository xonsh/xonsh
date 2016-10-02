#!/usr/bin/env python3
"""A package-based, source code amalgamater."""
import os
import sys
import pprint
from itertools import repeat
from collections import namedtuple
from collections.abc import Mapping
from ast import parse, walk, Import, ImportFrom

__version__ = '0.1.2'

ModNode = namedtuple('ModNode', ['name', 'pkgdeps', 'extdeps', 'futures'])
ModNode.__doc__ = """Module node for dependency graph.

Attributes
----------
name : str
    Module name.
pkgdeps : frozenset of str
    Module dependencies in the same package.
extdeps : frozenset of str
    External module dependencies from outside of the package.
futures : frozenset of str
    Import directive names antecedent to 'from __future__ import'
"""


class SourceCache(Mapping):
    """Stores / loads source code for files based on package and module names."""

    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)

    def __getitem__(self, key):
        d = self._d
        if key in d:
            return d[key]
        pkg, name = key
        pkgdir = pkg.replace('.', os.sep)
        fname = pkgdir + os.sep + name + '.py'
        with open(fname, encoding='utf-8', errors='surrogateescape') as f:
            raw = f.read()
        d[key] = raw
        return raw

    def __iter__(self):
        yield from self._d

    def __len__(self):
        return len(self._d)


SOURCES = SourceCache()


class GlobalNames(object):
    """Stores globally defined names that have been seen on ast nodes."""

    impnodes = frozenset(['import', 'importfrom'])

    def __init__(self, pkg='<pkg>'):
        self.cache = {}
        self.pkg = pkg
        self.module = '<mod>'
        self.topnode = None

    def warn_duplicates(self):
        s = ''
        for key in sorted(self.cache.keys()):
            val = self.cache[key]
            if len(val) < 2:
                continue
            val = sorted(val)
            if all([val[0][0] == x[0] for x in val[1:]]):
                continue
            s += 'WARNING: {0!r} defined in multiple locations:\n'.format(key)
            for loc in val:
                s += '  {}:{} ({})\n'.format(*loc)
        if len(s) > 0:
            print(s, end='', flush=True, file=sys.stderr)

    def entry(self, name, lineno):
        if name.startswith('__'):
            return
        topnode = self.topnode
        e = (self.pkg + '.' + self.module, lineno, topnode)
        if name in self.cache:
            if topnode in self.impnodes and \
                    all([topnode == x[2] for x in self.cache[name]]):
                return
            self.cache[name].add(e)
        else:
            self.cache[name] = set([e])

    def add(self, node, istopnode=False):
        """Adds the names from the node to the cache."""
        nodename = node.__class__.__name__.lower()
        if istopnode:
            self.topnode = nodename
        meth = getattr(self, '_add_' + nodename, None)
        if meth is not None:
            meth(node)

    def _add_name(self, node):
        self.entry(node.id, node.lineno)

    def _add_tuple(self, node):
        for x in node.elts:
            self.add(x)

    def _add_assign(self, node):
        for target in node.targets:
            self.add(target)

    def _add_functiondef(self, node):
        self.entry(node.name, node.lineno)

    def _add_classdef(self, node):
        self.entry(node.name, node.lineno)

    def _add_import(self, node):
        lineno = node.lineno
        for target in node.names:
            if target.asname is None:
                name, _, _ = target.name.partition('.')
            else:
                name = target.asname
            self.entry(name, lineno)

    def _add_importfrom(self, node):
        pkg, _ = resolve_package_module(node.module, self.pkg, node.level)
        if pkg == self.pkg:
            return
        lineno = node.lineno
        for target in node.names:
            if target.asname is None:
                name = target.name
            else:
                name = target.asname
            self.entry(name, lineno)

    def _add_with(self, node):
        for item in node.items:
            if item.optional_vars is None:
                continue
            self.add(item.optional_vars)
        for child in node.body:
            self.add(child, istopnode=True)

    def _add_for(self, node):
        self.add(node.target)
        for child in node.body:
            self.add(child, istopnode=True)

    def _add_while(self, node):
        for child in node.body:
            self.add(child, istopnode=True)

    def _add_if(self, node):
        for child in node.body:
            self.add(child, istopnode=True)
        for child in node.orelse:
            self.add(child, istopnode=True)

    def _add_try(self, node):
        for child in node.body:
            self.add(child, istopnode=True)


def module_is_package(module, pkg, level):
    """Returns whether or not the module name refers to the package."""
    if level == 0:
        return module == pkg
    elif level == 1:
        return module is None
    else:
        return False


def module_from_package(module, pkg, level):
    """Returns whether or not a module is from the package."""
    if level == 0:
        return module.startswith(pkg + '.')
    elif level == 1:
        return True
    else:
        return False


def resolve_package_module(module, pkg, level, default=None):
    """Returns a 2-tuple of package and module name, even for relative
    imports
    """
    if level == 0:
        p, _, m = module.rpartition('.')
    elif level == 1:
        p = pkg
        m = module or default
    else:
        p = m = None
    return p, m


def make_node(name, pkg, allowed, glbnames):
    """Makes a node by parsing a file and traversing its AST."""
    raw = SOURCES[pkg, name]
    tree = parse(raw, filename=name)
    # we only want to deal with global import statements
    pkgdeps = set()
    extdeps = set()
    futures = set()
    glbnames.module = name
    for a in tree.body:
        glbnames.add(a, istopnode=True)
        if isinstance(a, Import):
            for n in a.names:
                p, dot, m = n.name.rpartition('.')
                if p == pkg and m in allowed:
                    pkgdeps.add(m)
                else:
                    extdeps.add(n.name)
        elif isinstance(a, ImportFrom):
            if module_is_package(a.module, pkg, a.level):
                pkgdeps.update(n.name for n in a.names if n.name in allowed)
            elif module_from_package(a.module, pkg, a.level):
                p, m = resolve_package_module(a.module, pkg, a.level,
                                              default=a.names[0].name)
                if p == pkg and m in allowed:
                    pkgdeps.add(m)
                else:
                    extdeps.add(a.module)
            elif a.module == '__future__':
                futures.update(n.name for n in a.names)
    return ModNode(name, frozenset(pkgdeps), frozenset(extdeps),
                   frozenset(futures))


def make_graph(pkg, exclude=None):
    """Create a graph (dict) of module dependencies."""
    graph = {}
    pkgdir = pkg.replace('.', os.sep)
    allowed = set()
    files = os.listdir(pkgdir)
    for fname in files:
        base, ext = os.path.splitext(fname)
        if base.startswith('__') or ext != '.py':
            continue
        allowed.add(base)
    if exclude:
        allowed -= exclude
    glbnames = GlobalNames(pkg=pkg)
    for base in allowed:
        graph[base] = make_node(base, pkg, allowed, glbnames)
    glbnames.warn_duplicates()
    return graph


def depsort(graph):
    """Sort modules by dependency."""
    remaining = set(graph.keys())
    seder = []
    solved = set()
    while 0 < len(remaining):
        nodeps = {m for m in remaining if len(graph[m].pkgdeps - solved) == 0}
        if len(nodeps) == 0:
            msg = ('\nsolved order = {0}\nremaining = {1}\nCycle detected in '
                   'module graph!').format(pprint.pformat(seder),
                                           pprint.pformat(remaining))
            raise RuntimeError(msg)
        solved |= nodeps
        remaining -= nodeps
        seder += sorted(nodeps)
    return seder


LAZY_IMPORTS = """
from sys import modules as _modules
from types import ModuleType as _ModuleType
from importlib import import_module as _import_module


class _LazyModule(_ModuleType):

    def __init__(self, pkg, mod, asname=None):
        '''Lazy module 'pkg.mod' in package 'pkg'.'''
        self.__dct__ = {
            'loaded': False,
            'pkg': pkg,  # pkg
            'mod': mod,  # pkg.mod
            'asname': asname,  # alias
            }

    @classmethod
    def load(cls, pkg, mod, asname=None):
        if mod in _modules:
            key = pkg if asname is None else mod
            return _modules[key]
        else:
            return cls(pkg, mod, asname)

    def __getattribute__(self, name):
        if name == '__dct__':
            return super(_LazyModule, self).__getattribute__(name)
        dct = self.__dct__
        mod = dct['mod']
        if dct['loaded']:
            m = _modules[mod]
        else:
            m = _import_module(mod)
            glbs = globals()
            pkg = dct['pkg']
            asname = dct['asname']
            if asname is None:
                glbs[pkg] = m = _modules[pkg]
            else:
                glbs[asname] = m
            dct['loaded'] = True
        return getattr(m, name)

"""


def get_lineno(node, default=0):
    """Gets the lineno of a node or returns the default."""
    return getattr(node, 'lineno', default)


def min_line(node):
    """Computes the minimum lineno."""
    node_line = get_lineno(node)
    return min(map(get_lineno, walk(node), repeat(node_line)))


def format_import(names):
    """Format an import line"""
    parts = []
    for _, name, asname in names:
        if asname is None:
            parts.append(name)
        else:
            parts.append(name + ' as ' + asname)
    line = 'import ' + ', '.join(parts) + '\n'
    return line


def format_lazy_import(names):
    """Formats lazy import lines"""
    lines = ''
    for _, name, asname in names:
        pkg, _, _ = name.partition('.')
        if asname is None:
            line = '{pkg} = _LazyModule.load({pkg!r}, {mod!r})\n'
        else:
            line = '{asname} = _LazyModule.load({pkg!r}, {mod!r}, {asname!r})\n'
        lines += line.format(pkg=pkg, mod=name, asname=asname)
    return lines


def format_from_import(names):
    """Format a from import line"""
    parts = []
    for _, module, name, asname in names:
        if asname is None:
            parts.append(name)
        else:
            parts.append(name + ' as ' + asname)
    line = 'from ' + module
    line += ' import ' + ', '.join(parts) + '\n'
    return line


def rewrite_imports(name, pkg, order, imps):
    """Rewrite the global imports in the file given the amalgamation."""
    raw = SOURCES[pkg, name]
    tree = parse(raw, filename=name)
    replacements = []  # list of (startline, stopline, str) tuples
    # collect replacements in forward direction
    for a, b in zip(tree.body, tree.body[1:] + [None]):
        if not isinstance(a, (Import, ImportFrom)):
            continue
        start = min_line(a) - 1
        stop = len(tree.body) if b is None else min_line(b) - 1
        if isinstance(a, Import):
            keep = []
            for n in a.names:
                p, dot, m = n.name.rpartition('.')
                if p == pkg and m in order:
                    msg = ('Cannot amalgamate almagate import of '
                           'amalgamated module:\n\n  import {0}.{1}\n'
                           '\nin {0}/{2}.py').format(pkg, n.name, name)
                    raise RuntimeError(msg)
                imp = (Import, n.name, n.asname)
                if imp not in imps:
                    imps.add(imp)
                    keep.append(imp)
            if len(keep) == 0:
                s = ', '.join(n.name for n in a.names)
                s = '# amalgamated ' + s + '\n'
            else:
                s = format_lazy_import(keep)
            replacements.append((start, stop, s))
        elif isinstance(a, ImportFrom):
            p, m = resolve_package_module(a.module, pkg, a.level, default='')
            if module_is_package(a.module, pkg, a.level):
                for n in a.names:
                    if n.name in order:
                        msg = ('Cannot amalgamate import of '
                               'amalgamated module:\n\n  from {0} import {1}\n'
                               '\nin {0}/{2}.py').format(pkg, n.name, name)
                        raise RuntimeError(msg)
            elif p == pkg and m in order:
                replacements.append((start, stop,
                                     '# amalgamated ' + p + '.' + m + '\n'))
            elif a.module == '__future__':
                replacements.append((start, stop,
                                     '# amalgamated __future__ directive\n'))
            else:
                keep = []
                for n in a.names:
                    imp = (ImportFrom, a.module, n.name, n.asname)
                    if imp not in imps:
                        imps.add(imp)
                        keep.append(imp)
                if len(keep) == len(a.names):
                    continue  # all new imports
                elif len(keep) == 0:
                    s = ', '.join(n.name for n in a.names)
                    s = '# amalgamated from ' + a.module + ' import ' + s + '\n'
                else:
                    s = format_from_import(keep)
                replacements.append((start, stop, s))
    # apply replacements in reverse
    lines = raw.splitlines(keepends=True)
    for start, stop, s in replacements[::-1]:
        lines[start] = s
        for i in range(stop - start - 1):
            del lines[start+1]
    return ''.join(lines)


def sorted_futures(graph):
    """Returns a sorted, unique list of future imports."""
    f = set()
    for value in graph.values():
        f |= value.futures
    return sorted(f)


def amalgamate(order, graph, pkg):
    """Create amalgamated source."""
    src = ('\"\"\"Amalgamation of {0} package, made up of the following '
           'modules, in order:\n\n* ').format(pkg)
    src += '\n* '.join(order)
    src += '\n\n\"\"\"\n'
    futures = sorted_futures(graph)
    if len(futures) > 0:
        src += 'from __future__ import ' + ', '.join(futures) + '\n'
    src += LAZY_IMPORTS
    imps = set()
    for name in order:
        lines = rewrite_imports(name, pkg, order, imps)
        src += '#\n# ' + name + '\n#\n' + lines + '\n'
    return src


def write_amalgam(src, pkg):
    """Write out __amalgam__.py file"""
    pkgdir = pkg.replace('.', os.sep)
    fname = os.path.join(pkgdir, '__amalgam__.py')
    with open(fname, 'w', encoding='utf-8', errors='surrogateescape') as f:
        f.write(src)


def _init_name_lines(pkg):
    pkgdir = pkg.replace('.', os.sep)
    fname = os.path.join(pkgdir, '__init__.py')
    with open(fname, encoding='utf-8', errors='surrogateescape') as f:
        raw = f.read()
    lines = raw.splitlines()
    return fname, lines


def read_exclude(pkg):
    """reads in modules to exclude from __init__.py"""
    _, lines = _init_name_lines(pkg)
    exclude = set()
    for line in lines:
        if line.startswith('# amalgamate exclude'):
            exclude.update(line.split()[3:])
    return exclude


FAKE_LOAD = """
import os as _os
if _os.getenv('{debug}', ''):
    pass
else:
    import sys as _sys
    try:
        from {pkg} import __amalgam__
        {load}
        del __amalgam__
    except ImportError:
        pass
    del _sys
del _os
""".strip()


def rewrite_init(pkg, order, debug='DEBUG'):
    """Rewrites the init file to insert modules."""
    fname, lines = _init_name_lines(pkg)
    start, stop = -1, -1
    for i, line in enumerate(lines):
        if line.startswith('# amalgamate end'):
            stop = i
        elif line.startswith('# amalgamate'):
            start = i
    t = ("{1} = __amalgam__\n        "
         "_sys.modules['{0}.{1}'] = __amalgam__")
    load = '\n        '.join(t.format(pkg, m) for m in order)
    s = FAKE_LOAD.format(pkg=pkg, load=load, debug=debug)
    if start + 1 == stop:
        lines.insert(stop, s)
    else:
        lines[start+1] = s
        lines = lines[:start+2] + lines[stop:]
    init = '\n'.join(lines) + '\n'
    with open(fname, 'w', encoding='utf-8', errors='surrogateescape') as f:
        f.write(init)


def main(args=None):
    if args is None:
        args = sys.argv
    debug = 'DEBUG'
    for pkg in args[1:]:
        if pkg.startswith('--debug='):
            debug = pkg[8:]
            continue
        print('Amalgamating ' + pkg)
        exclude = read_exclude(pkg)
        print('  excluding {}'.format(pprint.pformat(exclude or None)))
        graph = make_graph(pkg, exclude=exclude)
        order = depsort(graph)
        src = amalgamate(order, graph, pkg)
        write_amalgam(src, pkg)
        rewrite_init(pkg, order, debug=debug)
        print('  collapsed {} modules'.format(len(order)))


if __name__ == '__main__':
    main()
