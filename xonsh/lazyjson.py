"""Implements a lazy JSON file class that wraps around json data."""
from __future__ import print_function, unicode_literals
from collections import Mapping, Sequence
try:
    import simplejson as json
except ImportError:
    import json

from xonsh.tools import string_types


class LazyJSON(object):
    """Represents a lazy json file."""


def _to_json_with_size(obj, offset=0):
    if isinstance(obj, string_types):
        s = json.dumps(obj)
        o = offset
        n = size = len(s.encode())  # size in bytes
    elif isinstance(obj, Mapping):
        s = '{'
        j = offset + 1
        o = {}
        size = {}
        for key, val in obj.items():
            s_k, o_k, n_k, size_k = _to_json_with_size(key, offset=j)
            s += s_k + ': '
            j += n_k + 2
            s_v, o_v, n_v, size_v = _to_json_with_size(val, offset=j)
            o[key] = j
            size[key] = size_v
            s += s_x + ', '
            j += n_x + 2
        s = s[:-2]
        s += '}\n'
        n = len(s)
        
    elif isinstance(obj, Sequence):
        s = '['
        j = offset + 1
        o = []
        size = []
        for x in obj:
            s_x, o_x, n_x, size_x = _to_json_with_size(x, offset=j)
            o.append(j)
            size.append(size_x)
            s += s_x + ', '
            j += n_x + 2
        s = s[:-2]
        s += ']\n'
        n = len(s)
    else:
        s = json.dumps(obj)
        o = offset
        n = size = len(s)
    return s, o, n, size


def index(obj):
    """Creates an index for a JSON file."""
    index = {}
    s, index['offset'], _, index['size'] = _to_json_with_size(obj)
    return s, index


def dumps(obj):
    """"""
    
    