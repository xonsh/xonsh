"""Implements a lazy JSON file class that wraps around json data."""
from __future__ import print_function, unicode_literals
from collections import Mapping, Sequence
from contextlib import contextmanager
try:
    import simplejson as json
except ImportError:
    import json

from xonsh.tools import string_types


def _to_json_with_size(obj, offset=0, sort_keys=False):
    if isinstance(obj, string_types):
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
            o.append(j)
            size.append(size_x)
            s += s_x + ', '
            j += n_x + 2
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



#class Node(Mapping, Sequence):

#class LazyJSON(Node):
class LazyJSON(object):
    """Represents a lazy json file."""

    def __init__(self, f, reopen=True):
        """Parameters
        ----------
        f : file handle or str
            JSON file to open.
        reopen : bool
            Whether new file handle should be opened for each load.
        """
        self._f = f
        self.reopen = reopen
        if not reopen and isinstance(f, string_types):
            self._f = open(f, 'r')
        self._load_index()

    def __del__(self):
        if not self.reopen:
            self._f.close()

    @contextmanager
    def _open(self, *args, **kwargs):
        if self.reopen and isinstance(self._f, string_types):
            f = open(self._f, *args, **kwargs)
            yield f
            f.close()
        else:
            yield self._f

    def _load_index(self):
        """Loads the index from the start of the file."""
        with self._open as f:
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
