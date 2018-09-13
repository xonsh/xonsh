"""Base class for chaining DBs"""

import itertools

from collections import ChainMap
from collections.abc import MutableMapping, MutableSequence


class ChainDBDefaultType(object):
    """Singleton for representing when no default value is given."""

    __inst = None

    def __new__(cls):
        if ChainDBDefaultType.__inst is None:
            ChainDBDefaultType.__inst = object.__new__(cls)
        return ChainDBDefaultType.__inst


ChainDBDefault = ChainDBDefaultType()


class ChainDB(ChainMap):
    """ A ChainMap who's ``_getitem__`` returns either a ChainDB or
    the result"""

    def __getitem__(self, key):
        res = None
        results = []
        # Try to get all the data from all the mappings
        for mapping in self.maps:
            results.append(mapping.get(key, ChainDBDefault))
        # if all the results are mapping create a ChainDB
        if all([isinstance(result, MutableMapping) for result in results]):
            for result in results:
                if res is None:
                    res = ChainDB(result)
                else:
                    res.maps.append(result)
        elif all([isinstance(result, MutableSequence) for result in results]):
            return list(itertools.chain(*results))
        else:
            for result in reversed(results):
                if result is not ChainDBDefault:
                    return result
            raise KeyError("{} is none of the current mappings".format(key))
        return res

    def __setitem__(self, key, value):
        if key not in self:
            super().__setitem__(key, value)
        else:
            # Try to get all the data from all the mappings
            for mapping in reversed(self.maps):
                if key in mapping:
                    mapping[key] = value


def _convert_to_dict(cm):
    if isinstance(cm, (ChainMap, ChainDB)):
        r = {}
        for k, v in cm.items():
            r[k] = _convert_to_dict(v)
        return r
    else:
        return cm
