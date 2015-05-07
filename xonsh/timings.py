"""Timing related functionality for the xonsh shell."""
import gc
import time
import timeit
import builtins
import itertools


# The following time_it alias and Timer was forked from the IPython project:
# * Copyright (c) 2008-2014, IPython Development Team
# * Copyright (C) 2001-2007 Fernando Perez <fperez@colorado.edu>
# * Copyright (c) 2001, Janko Hauser <jhauser@zscout.de>
# * Copyright (c) 2001, Nathaniel Gray <n8gray@caltech.edu>
class Timer(timeit.Timer):
    """Timer class that explicitly uses self.inner
    which is an undocumented implementation detail of CPython,
    not shared by PyPy.
    """
    # Timer.timeit copied from CPython 3.4.2
    def timeit(self, number=timeit.default_number):
        """Time 'number' executions of the main statement.
        To be precise, this executes the setup statement once, and
        then returns the time it takes to execute the main statement
        a number of times, as a float measured in seconds.  The
        argument is the number of times through the loop, defaulting
        to one million.  The main statement, the setup statement and
        the timer function to be used are passed to the constructor.
        """
        it = itertools.repeat(None, number)
        gcold = gc.isenabled()
        gc.disable()
        try:
            timing = self.inner(it, self.timer)
        finally:
            if gcold:
                gc.enable()
        return timing


INNER_TEMPLATE = """
def inner(_it, _timer):
    #setup
    _t0 = _timer()
    for _i in _it:
        {stmt}
    _t1 = _timer()
    return _t1 - _t0
"""

def time_it(args, stdin=None):
    """Runs timing study on arguments."""
    timer = Timer(timer=timefunc)
    stmt = ' '.join(args)
    innerstr = INNER_TEMPLATE.format(stmt=stmt)
    inner = builtins.compilex(innerstr, )
    return

