# -*- coding: utf-8 -*-
"""Implements a lazy JSON file class that wraps around json data."""
import io
import json
from collections import Mapping, Sequence
from contextlib import contextmanager
import weakref



def _to_json_with_size(obj, offset=0, sort_keys=False):
    if isinstance(obj, str):
        s = json.dumps(obj)
        o = offset
        n = size = len(s.encode())  # size in bytes
    elif isinstance(obj, Mapping):
        s = '{'
        j = offset + 1
        o = {}
        size = {}
        items = sorted(obj.items()) if sort_keys else obj.items()
        for key, val in items:
            s_k, o_k, n_k, size_k = _to_json_with_size(key, offset=j,
                                                       sort_keys=sort_keys)
            s += s_k + ': '
            j += n_k + 2
            s_v, o_v, n_v, size_v = _to_json_with_size(val, offset=j,
                                                       sort_keys=sort_keys)
            o[key] = o_v
            size[key] = size_v
            s += s_v + ', '
            j += n_v + 2
        if s.endswith(', '):
            s = s[:-2]
        s += '}\n'
        n = len(s)
        o['__total__'] = offset
        size['__total__'] = n
    elif isinstance(obj, Sequence):
        s = '['
        j = offset + 1
        o = []
        size = []
        for x in obj:
            s_x, o_x, n_x, size_x = _to_json_with_size(x, offset=j,
                                                       sort_keys=sort_keys)
            o.append(o_x)
            size.append(size_x)
            s += s_x + ', '
            j += n_x + 2
        if s.endswith(', '):
            s = s[:-2]
        s += ']\n'
        n = len(s)
        o.append(offset)
        size.append(n)
    else:
        s = json.dumps(obj, sort_keys=sort_keys)
        o = offset
        n = size = len(s)
    return s, o, n, size


def index(obj, sort_keys=False):
    """Creates an index for a JSON file."""
    idx = {}
    json_obj = _to_json_with_size(obj, sort_keys=sort_keys)
    s, idx['offsets'], _, idx['sizes'] = json_obj
    return s, idx


JSON_FORMAT = \
"""{{"locs": [{iloc:>10}, {ilen:>10}, {dloc:>10}, {dlen:>10}],
 "index": {index},
 "data": {data}
}}
"""


def dumps(obj, sort_keys=False):
    """Dumps an object to JSON with an index."""
    data, idx = index(obj, sort_keys=sort_keys)
    jdx = json.dumps(idx, sort_keys=sort_keys)
    iloc = 69
    ilen = len(jdx)
    dloc = iloc + ilen + 11
    dlen = len(data)
    s = JSON_FORMAT.format(index=jdx, data=data, iloc=iloc, ilen=ilen,
                           dloc=dloc, dlen=dlen)
    return s


def dump(obj, fp, sort_keys=False):
    """Dumps an object to JSON file."""
    s = dumps(obj, sort_keys=sort_keys)
    fp.write(s)


class Node(Mapping, Sequence):
    """A proxy node for JSON nodes. Acts as both sequence and mapping."""

    def __init__(self, offsets, sizes, root):
        """Parameters
        ----------
        offsets : dict, list, or int
            offsets of corresponding data structure, in bytes
        sizes : dict, list, or int
            sizes of corresponding data structure, in bytes
        root : weakref.proxy of LazyJSON
            weakref back to root node, which should be a LazyJSON object.
        """
        self.offsets = offsets
        self.sizes = sizes
        self.root = root
        self.is_mapping = isinstance(self.offsets, Mapping)
        self.is_sequence = isinstance(self.offsets, Sequence)

    def __len__(self):
        # recall that for maps, the '__total__' key is added and for
        # sequences the last element represents the total size/offset.
        return len(self.sizes) - 1

    def load(self):
        """Returns the Python data structure represented by the node."""
        if self.is_mapping:
            offset = self.offsets['__total__']
            size = self.sizes['__total__']
        elif self.is_sequence:
            offset = self.offsets[-1]
            size = self.sizes[-1]
        elif isinstance(self.offsets, int):
            offset = self.offsets
            size = self.sizes
        return self._load_or_node(offset, size)

    def _load_or_node(self, offset, size):
        if isinstance(offset, int):
            with self.root._open(newline='\n') as f:
                f.seek(self.root.dloc + offset)
                s = f.read(size)
            val = json.loads(s)
        elif isinstance(offset, (Mapping, Sequence)):
            val = Node(offset, size, self.root)
        else:
            raise TypeError('incorrect types for offset node')
        return val

    def _getitem_mapping(self, key):
        if key == '__total__':
            raise KeyError('"__total__" is a special LazyJSON key!')
        offset = self.offsets[key]
        size = self.sizes[key]
        return self._load_or_node(offset, size)

    def _getitem_sequence(self, key):
        if isinstance(key, int):
            rtn = self._load_or_node(self.offsets[key], self.sizes[key])
        elif isinstance(key, slice):
            key = slice(*key.indices(len(self)))
            rtn = list(map(self._load_or_node, self.offsets[key],
                           self.sizes[key]))
        else:
            raise TypeError('only integer indexing available')
        return rtn

    def __getitem__(self, key):
        if self.is_mapping:
            rtn = self._getitem_mapping(key)
        elif self.is_sequence:
            rtn = self._getitem_sequence(key)
        else:
            raise NotImplementedError
        return rtn

    def __iter__(self):
        if self.is_mapping:
            keys = set(self.offsets.keys())
            keys.discard('__total__')
            yield from iter(keys)
        elif self.is_sequence:
            i = 0
            n = len(self)
            while i < n:
                yield self._load_or_node(self.offsets[i], self.sizes[i])
                i += 1
        else:
            raise NotImplementedError


class LazyJSON(Node):
    """Represents a lazy json file. Can be used like a normal Python
    dict or list.
    """

    def __init__(self, f, reopen=True):
        """Parameters
        ----------
        f : file handle or str
            JSON file to open.
        reopen : bool, optional
            Whether new file handle should be opened for each load.
        """
        self._f = f
        self.reopen = reopen
        if not reopen and isinstance(f, str):
            self._f = open(f, 'r', newline='\n')
        self._load_index()
        self.root = weakref.proxy(self)
        self.is_mapping = isinstance(self.offsets, Mapping)
        self.is_sequence = isinstance(self.offsets, Sequence)

    def __del__(self):
        self.close()

    def close(self):
        """Close the file handle, if appropriate."""
        if not self.reopen and isinstance(self._f, io.IOBase):
            self._f.close()

    @contextmanager
    def _open(self, *args, **kwargs):
        if self.reopen and isinstance(self._f, str):
            f = open(self._f, *args, **kwargs)
            yield f
            f.close()
        else:
            yield self._f

    def _load_index(self):
        """Loads the index from the start of the file."""
        with self._open(newline='\n') as f:
            # read in the location data
            f.seek(9)
            locs = f.read(48)
            locs = json.loads(locs)
            self.iloc, self.ilen, self.dloc, self.dlen = locs
            # read in the index
            f.seek(self.iloc)
            idx = f.read(self.ilen)
            idx = json.loads(idx)
        self.offsets = idx['offsets']
        self.sizes = idx['sizes']

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

