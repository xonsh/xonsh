from unittest import TestCase, main

from multiprocessing import Process, Queue
from six.moves.queue import Empty

import sys
import locale

if ".." not in sys.path:
    sys.path.insert(0, "..")

from ply.lex import lex
from ply.cpp import *


def preprocessing(in_, out_queue):
    out = None

    try:
        p = Preprocessor(lex())
        p.parse(in_)
        tokens = [t.value for t in p.parser]
        out = "".join(tokens)
    finally:
        out_queue.put(out)

class CPPTests(TestCase):
    "Tests related to ANSI-C style lexical preprocessor."

    def __test_preprocessing(self, in_, expected, time_limit = 1.0):
        out_queue = Queue()

        preprocessor = Process(
            name = "PLY`s C preprocessor",
            target = preprocessing,
            args = (in_, out_queue)
        )

        preprocessor.start()

        try:
            out = out_queue.get(timeout = time_limit)
        except Empty:
            preprocessor.terminate()
            raise RuntimeError("Time limit exceeded!")
        else:
            self.assertMultiLineEqual(out, expected)

    def test_infinite_argument_expansion(self):
        # CPP does not drags set of currently expanded macros through macro
        # arguments expansion. If there is a match between an argument value
        # and name of an already expanded macro then CPP falls into infinite
        # recursion.
        self.__test_preprocessing("""\
#define a(x) x
#define b a(b)
b
"""         , """\


b"""
        )


    def test_concatenation(self):
        self.__test_preprocessing("""\
#define a(x) x##_
#define b(x) _##x
#define c(x) _##x##_
#define d(x,y) _##x##y##_

a(i)
b(j)
c(k)
d(q,s)"""
            , """\





i_
_j
_k_
_qs_"""
        )

    def test_deadloop_macro(self):
        # If there is a word which equals to name of a parametrized macro, then
        # attempt to expand such word as a macro manages the parser to fall
        # into an infinite loop.

        self.__test_preprocessing("""\
#define a(x) x

a;"""
            , """\


a;"""
        )

    def test_index_error(self):
        # If there are no tokens after a word ("a") which equals to name of
        # a parameterized macro, then attempt to expand this word leads to
        # IndexError.

        self.__test_preprocessing("""\
#define a(x) x

a"""
            , """\


a"""
        )

    def test_evalexpr(self):
        # #if 1 != 2 is not processed correctly; undefined values are converted
        # to 0L instead of 0 (issue #195)
        #
        self.__test_preprocessing("""\
#if (1!=0) && (!x || (!(1==2)))
a;
#else
b;
#endif
"""
            , """\

a;

"""
        )

    def test_include_nonascii(self):
        # Issue #196: #included files are read using the current locale's
        # getdefaultencoding. if a #included file contains non-ascii characters,
        # while default encoding is e.g. US_ASCII, this causes an error
        locale.setlocale(locale.LC_ALL, 'C')
        self.__test_preprocessing("""\
#include "test_cpp_nonascii.c"
x;

"""
            , """\

 
1;
"""
        )

main()
