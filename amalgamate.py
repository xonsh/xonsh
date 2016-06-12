"""A package-based, source code amalgamater."""
import os
import sys
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

    def __init__(self, *args, **kwarg):
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

def make_node(name, pkg):
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
                if n.name.startswith(pkgdot):
                    pkgdeps.add(n.name.rpartition('.')[-1])
                else:
                    extdeps.add(n.name)
        elif isinstance(a, ImportFrom):
            if a.module == pkg:
                pkgdeps.update(n.name for n in a.names)
            elif a.module.startswith(pkgdot):
                p, dot, m = a.module.rpartition('.')
                if p == pkg:
                    pkgdeps.add(m)
                else:
                    extdeps.add(a.module)
    return ModNode(name, frozenset(pkgdeps), frozenset(extdeps))



def make_graph(pkg):
    """Create a graph (dict) of module dependencies."""
    graph = {}
    pkgdir = pkg.replace('.', os.sep)
    for fname in os.listdir(pkgdir):
        base, ext = os.path.splitext(fname)
        if base.startswith('__') or ext != '.py':
            continue
        graph[base] = make_node(base, pkg)
    return graph



def main(args=None):
    if args is None:
        args = sys.argv
    for pkg in args:
        graph = make_graph(pkg)
        print(graph)


if __name__ == '__main__':
    main()