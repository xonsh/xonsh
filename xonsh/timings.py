# -*- coding: utf-8 -*-
"""Timing related functionality for the xonsh shell.

The following time_it alias and Timer was forked from the IPython project:
* Copyright (c) 2008-2014, IPython Development Team
* Copyright (C) 2001-2007 Fernando Perez <fperez@colorado.edu>
* Copyright (c) 2001, Janko Hauser <jhauser@zscout.de>
* Copyright (c) 2001, Nathaniel Gray <n8gray@caltech.edu>
"""
import os
import gc
import sys
import math
import time
import timeit
import builtins
import itertools

from xonsh.lazyasd import lazyobject, lazybool
from xonsh.events import events
from xonsh.platform import ON_WINDOWS


@lazybool
def _HAVE_RESOURCE():
    try:
        import resource as r
        have = True
    except ImportError:
        # There is no distinction of user/system time under windows, so we
        # just use time.perf_counter() for everything...
        have = False
    return have


@lazyobject
def resource():
    import resource as r
    return r


@lazyobject
def clocku():
    if _HAVE_RESOURCE:
        def clocku():
            """clocku() -> floating point number
            Return the *USER* CPU time in seconds since the start of the
            process."""
            return resource.getrusage(resource.RUSAGE_SELF)[0]
    else:
        clocku = time.perf_counter
    return clocku


@lazyobject
def clocks():
    if _HAVE_RESOURCE:
        def clocks():
            """clocks() -> floating point number
            Return the *SYSTEM* CPU time in seconds since the start of the
            process."""
            return resource.getrusage(resource.RUSAGE_SELF)[1]
    else:
        clocks = time.perf_counter
    return clocks


@lazyobject
def clock():
    if _HAVE_RESOURCE:
        def clock():
            """clock() -> floating point number
            Return the *TOTAL USER+SYSTEM* CPU time in seconds since the
            start of the process."""
            u, s = resource.getrusage(resource.RUSAGE_SELF)[:2]
            return u + s
    else:
        clock = time.perf_counter
    return clock


@lazyobject
def clock2():
    if _HAVE_RESOURCE:
        def clock2():
            """clock2() -> (t_user,t_system)
            Similar to clock(), but return a tuple of user/system times."""
            return resource.getrusage(resource.RUSAGE_SELF)[:2]
    else:
        def clock2():
            """Under windows, system CPU time can't be measured.
            This just returns perf_counter() and zero."""
            return time.perf_counter(), 0.0
    return clock2


def format_time(timespan, precision=3):
    """Formats the timespan in a human readable form"""
    if timespan >= 60.0:
        # we have more than a minute, format that in a human readable form
        parts = [("d", 60 * 60 * 24), ("h", 60 * 60), ("min", 60), ("s", 1)]
        time = []
        leftover = timespan
        for suffix, length in parts:
            value = int(leftover / length)
            if value > 0:
                leftover = leftover % length
                time.append('{0}{1}'.format(str(value), suffix))
            if leftover < 1:
                break
        return " ".join(time)
    # Unfortunately the unicode 'micro' symbol can cause problems in
    # certain terminals.
    # See bug: https://bugs.launchpad.net/ipython/+bug/348466
    # Try to prevent crashes by being more secure than it needs to
    # E.g. eclipse is able to print a mu, but has no sys.stdout.encoding set.
    units = ["s", "ms", 'us', "ns"]  # the save value
    if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding:
        try:
            '\xb5'.encode(sys.stdout.encoding)
            units = ["s", "ms", '\xb5s', "ns"]
        except Exception:
            pass
    scaling = [1, 1e3, 1e6, 1e9]

    if timespan > 0.0:
        order = min(-int(math.floor(math.log10(timespan)) // 3), 3)
    else:
        order = 3
    return "{1:.{0}g} {2}".format(precision, timespan * scaling[order],
                                  units[order])


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


def timeit_alias(args, stdin=None):
    """Runs timing study on arguments."""
    # some real args
    number = 0
    quiet = False
    repeat = 3
    precision = 3
    # setup
    ctx = builtins.__xonsh_ctx__
    timer = Timer(timer=clock)
    stmt = ' '.join(args)
    innerstr = INNER_TEMPLATE.format(stmt=stmt)
    # Track compilation time so it can be reported if too long
    # Minimum time above which compilation time will be reported
    tc_min = 0.1
    t0 = clock()
    innercode = builtins.compilex(innerstr, filename='<xonsh-timeit>',
                                  mode='exec', glbs=ctx)
    tc = clock() - t0
    # get inner func
    ns = {}
    builtins.execx(innercode, glbs=ctx, locs=ns, mode='exec')
    timer.inner = ns['inner']
    # Check if there is a huge difference between the best and worst timings.
    worst_tuning = 0
    if number == 0:
        # determine number so that 0.2 <= total time < 2.0
        number = 1
        for _ in range(1, 10):
            time_number = timer.timeit(number)
            worst_tuning = max(worst_tuning, time_number / number)
            if time_number >= 0.2:
                break
            number *= 10
    all_runs = timer.repeat(repeat, number)
    best = min(all_runs) / number
    # print some debug info
    if not quiet:
        worst = max(all_runs) / number
        if worst_tuning:
            worst = max(worst, worst_tuning)
        # Check best timing is greater than zero to avoid a
        # ZeroDivisionError.
        # In cases where the slowest timing is lesser than 10 micoseconds
        # we assume that it does not really matter if the fastest
        # timing is 4 times faster than the slowest timing or not.
        if worst > 4 * best and best > 0 and worst > 1e-5:
            print(('The slowest run took {0:0.2f} times longer than the '
                   'fastest. This could mean that an intermediate result '
                   'is being cached.').format(worst / best))
        print("{0} loops, best of {1}: {2} per loop"
              .format(number, repeat, format_time(best, precision)))
        if tc > tc_min:
            print("Compiler time: {0:.2f} s".format(tc))
    return


_timings = {'start': clock()}


def setup_timings():
    global _timings
    if '--timings' in sys.argv:
        events.doc('on_timingprobe', """
        on_timingprobe(name: str) -> None

        Fired to insert some timings into the startuptime list
        """)

        @events.on_timingprobe
        def timing_on_timingprobe(name, **kw):
            global _timings
            _timings[name] = clock()

        @events.on_post_cmdloop
        def timing_on_post_cmdloop(**kw):
            global _timings
            _timings['on_post_cmdloop'] = clock()

        @events.on_post_init
        def timing_on_post_init(**kw):
            global _timings
            _timings['on_post_init'] = clock()

        @events.on_post_rc
        def timing_on_post_rc(**kw):
            global _timings
            _timings['on_post_rc'] = clock()

        @events.on_postcommand
        def timing_on_postcommand(**kw):
            global _timings
            _timings['on_postcommand'] = clock()

        @events.on_pre_cmdloop
        def timing_on_pre_cmdloop(**kw):
            global _timings
            _timings['on_pre_cmdloop'] = clock()

        @events.on_pre_rc
        def timing_on_pre_rc(**kw):
            global _timings
            _timings['on_pre_rc'] = clock()

        @events.on_precommand
        def timing_on_precommand(**kw):
            global _timings
            _timings['on_precommand'] = clock()

        @events.on_ptk_create
        def timing_on_ptk_create(**kw):
            global _timings
            _timings['on_ptk_create'] = clock()

        @events.on_chdir
        def timing_on_chdir(**kw):
            global _timings
            _timings['on_chdir'] = clock()

        @events.on_post_prompt
        def timing_on_post_prompt(**kw):
            global _timings
            _timings = {'on_post_prompt': clock()}

        @events.on_pre_prompt
        def timing_on_pre_prompt(**kw):
            global _timings
            _timings['on_pre_prompt'] = clock()
            times = list(_timings.items())
            times = sorted(times, key=lambda x: x[1])
            width = max(len(s) for s, _ in times) + 2
            header_format = '|{{:<{}}}|{{:^11}}|{{:^11}}|'.format(width)
            entry_format = '|{{:<{}}}|{{:^11.3f}}|{{:^11.3f}}|'.format(width)
            sepline = '|{}|{}|{}|'.format('-'*width, '-'*11, '-'*11)
            # Print result table
            print(' Debug level: {}'.format(os.getenv('XONSH_DEBUG', 'Off')))
            print(sepline)
            print(header_format.format('Event name', 'Time (s)', 'Delta (s)'))
            print(sepline)
            prevtime = tstart = times[0][1]
            for name, ts in times:
                print(entry_format.format(name, ts - tstart, ts - prevtime))
                prevtime = ts
            print(sepline)
