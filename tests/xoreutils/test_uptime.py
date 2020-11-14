#!/usr/bin/env python
# coding: utf8

import importlib
import sys
import time
from datetime import datetime
import unittest

sys.path.insert(0, ".")

from xonsh.xoreutils import uptime


boottime_helpers = [f for f in vars(uptime) if f.startswith("_boottime_")]
uptime_helpers = [f for f in vars(uptime) if f.startswith("_uptime_")]


class NormalTest(unittest.TestCase):
    """	
    This class just calls each of the functions normally and ensures they don't	
    do dumb things like throw exceptions or return complex numbers.	
    """

    def tearDown(self):
        """	
        __boottime affects how boottime() and its helpers work, and it may be	
        set as a side-effect by any function. To be on the safe side, just	
        reload the whole module every time.	
        """
        importlib.reload(uptime)

    def basic_test(self, func, rettypes):
        """	
        Calls a given function and checks if it returns something of a type	
        in the sequence rettypes.	
        """
        ret = func()
        self.assertTrue(any(isinstance(ret, t) for t in rettypes))

    def __getattr__(self, name):
        # I really don't feel like writing and maintaining over a dozen
        # essentially identical methods, and if there's a cleaner way to do
        # this, I couldn't find it in the unittest docs.
        if name.startswith("test_"):
            func = name[5:]
            if func == "uptime" or func in uptime_helpers:
                rettypes = (type(None), float, int)
            elif func == "boottime" or func in boottime_helpers:
                rettypes = (type(None), datetime)
            else:
                raise AttributeError()
            return lambda: self.basic_test(getattr(uptime, func), rettypes)
        else:
            return unittest.TestCase.__getattr__(self, name)


class BrokenCtypesTest(NormalTest):
    """	
    It's ridiculous how many platforms don't have ctypes. This class simulates	
    that.	
    """

    @classmethod
    def setUpClass(cls):
        uptime.ctypes = None
        delattr(uptime, "struct")
        delattr(uptime, "os")


class OtherTest(unittest.TestCase):
    def setUp(self):
        importlib.reload(uptime)

    def test_equality_guarantee(self):
        """	
        If uptime.uptime and uptime.boottime are the only functions called,	
        it is guaranteed that the uptime subtracted from the current time is	
        the reported boot time, or that both are None.	
        """
        # Test uptime.boottime() original function
        up = uptime.uptime()
        if up is None:
            self.assertTrue(uptime.boottime() is None)
        else:
            boot1 = datetime.fromtimestamp(int(time.time() - up))
            boot2 = uptime.boottime()
            self.assertTrue(boot1 == boot2)

        # Test uptime.boottime_timestamp() function add for xonsh
        up = uptime.uptime()
        if up is None:
            self.assertTrue(uptime.boottime() is None)
        else:
            boot1 = int(time.time() - up)
            boot2 = int(uptime.boottime_timestamp())
            self.assertTrue(boot1 == boot2)

    def test_broken_datetime(self):
        """	
        datetime was introduced in Python 2.3, and though we officially only	
        support Python 2.5+ (because of ctypes), there are some platforms that	
        only have older versions available for which we can still provide	
        meaningful answers (Plan 9, mostly).	
        Importing uptime shouldn't immediately fail for them, but calling	
        boottime and its helpers should raise a RuntimeError.	
        """
        uptime.datetime = None
        self.assertRaises(RuntimeError, uptime.boottime)
        for h in boottime_helpers:
            self.assertRaises(RuntimeError, getattr(uptime, h))


def run_suite(suite):
    """	
    unittest is basically a disaster, so let's do this ourselves.	
    """
    sys.stdout.write("Running %d tests... \n" % tests.countTestCases())

    res = unittest.TestResult()
    suite.run(res)

    if res.wasSuccessful():
        sys.stdout.write("Finished without errors.\n")
        return

    sys.stdout.write("\n")
    for problems, kind in ((res.errors, "error"), (res.failures, "failure")):
        if len(problems):
            head = "%d %s%s" % (len(problems), kind, "s" if len(problems) != 1 else "")
            sys.stdout.write("\033[1;31m%s\n%s\033[0m\n" % (head, "⎻" * len(head)))

        for problem in problems:
            func = problem[0]._testMethodName[5:]
            environ = (
                " (broken ctypes)" if isinstance(problem[0], BrokenCtypesTest) else ""
            )
            sys.stdout.write(
                "• \033[1m%s%s\033[0m failed with message:\n\n%s\n\n"
                % (
                    func,
                    environ,
                    "\n".join(["    " + s for s in problem[1].splitlines()]),
                )
            )

    sys.stdout.write(
        "%d tests completed successfully.\n"
        % (res.testsRun - len(res.failures) - len(res.errors))
    )


if __name__ == "__main__":
    tests = unittest.TestSuite()

    # uptime tests
    tests.addTests([NormalTest("test_uptime"), BrokenCtypesTest("test_uptime")])
    for helper in uptime_helpers:
        tests.addTests(
            [NormalTest("test_%s" % helper), BrokenCtypesTest("test_%s" % helper)]
        )

    # boottime tests
    tests.addTests([NormalTest("test_boottime"), BrokenCtypesTest("test_boottime")])
    for helper in boottime_helpers:
        tests.addTests(
            [NormalTest("test_%s" % helper), BrokenCtypesTest("test_%s" % helper)]
        )

    # Other tests
    tests.addTest(OtherTest("test_equality_guarantee"))
    tests.addTest(OtherTest("test_broken_datetime"))

    run_suite(tests)
