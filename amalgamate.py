"""A package-based, source code amalgamater."""
import os
import sys
import pprint
from itertools import repeat
from collections import namedtuple
from collections.abc import Mapping
from ast import parse, walk, literal_eval, Import, ImportFrom

ModNode = namedtuple('ModNode', ['name', 'pkgdeps', 'extdeps'])
ModNode.__doc__ = """Module node for dependency graph.

Attrributes
-----------
name : str
    Module name.
pkgdeps : frozenset of str
    Module dependencies in the same package.
extdeps : frozenset of str
    External module dependencies from outside of the package.
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
        with open(fname) as f:
            raw = f.read()
        d[key] = raw
        return raw

    def __iter__(self):
        yield from self._d

    def __len__(self):
        return len(self._d)


SOURCES = SourceCache()

def make_node(name, pkg, allowed):
    """Makes a node by parsing a file and traversing its AST."""
    raw = SOURCES[pkg, name]
    tree = parse(raw, filename=name)
    # we only want to deal with global import statements
    pkgdot = pkg + '.'
    pkgdeps = set()
    extdeps = set()
    for a in tree.body:
        if isinstance(a, Import):
            for n in a.names:
                p, dot, m = n.name.rpartition('.')
                if p == pkg and m in allowed:
                    pkgdeps.add(m)
                else:
                    extdeps.add(n.name)
        elif isinstance(a, ImportFrom):
            if a.module == pkg:
                pkgdeps.update(n.name for n in a.names if n.name in allowed)
            elif a.module.startswith(pkgdot):
                p, dot, m = a.module.rpartition('.')
                if p == pkg and m in allowed:
                    pkgdeps.add(m)
                else:
                    extdeps.add(a.module)
    return ModNode(name, frozenset(pkgdeps), frozenset(extdeps))



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
    for base in allowed:
        graph[base] = make_node(base, pkg, allowed)
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
    pkgdot = pkg + '.'
    raw = SOURCES[pkg, name]
    tree = parse(raw, filename=name)
    replacements = []  # list of (startline, stopline, str) tuples
    # collect replacements in forward direction
    for a, b in zip(tree.body, tree.body[1:] + [None]):
        if not isinstance(a, (Import, FromImport)):
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
            if len(keep) == len(a.names):
                continue  # all new imports
            elif len(keep) == 0:
                s = ', '.join(n.name for n in  a.names)
                s = '# amalgamated ' + s + '\n'
            else:
                s = format_import(keep)
            replacements.append((start, stop, s))
        elif isinstance(a, ImportFrom):
            p, dot, m = a.module.rpartition('.')
            if a.module == pkg:
                for n in a.names:
                    if n.name in order:
                        msg = ('Cannot amalgamate almagate import of '
                               'amalgamated module:\n\n  from {0} import {1}\n'
                               '\nin {0}/{2}.py').format(pkg, n.name, name)
                        raise RuntimeError(msg)
            elif a.module.startswith(pkgdot) and p == pkg and m in order:
                replacements.append((start, stop,
                                     '# amalgamated ' + a.module + '\n'))
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
                    s = ', '.join(n.name for n in  a.names)
                    s = '# amalgamated from ' a.module + ' import ' + s + '\n'
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



def amalgamate(order, graph, pkg):
    """Create amalgamated source."""
    src = ''
    imps = set()
    for name in order:
        lines = rewrite_imports(name, pkg, order, imps)
        src += '#\n# ' + name + '\n#\n' + lines + '\n'
    return src


def write_amalgam(src, pkg):
    """Write out __amalgam__.py file"""
    pkgdir = pkg.replace('.', os.sep)
    fname = os.path.join(pkgdir, '__amalgam__.py')
    with open(fname, 'w') as f:
        f.write(src)


def main(args=None):
    if args is None:
        args = sys.argv
    for pkg in args:
        graph = make_graph(pkg)
        order = depsort(graph)
        src = amalgam(order, graph, pkg)
        write_amalgam(src, pkg)


if __name__ == '__main__':
    main()