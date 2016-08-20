.. _tutorial_macros:

************************************
Tutorial: Macros
************************************
Bust out your DSLRs, people. It is time to closely examine macros!

What are macro instructions?
============================
In generic terms, a programming macro is a special kind of syntax that
replaces a smaller amount of code with a larger expression, syntax tree,
code object, etc after the macro has been evaluated.
In practice, macros pause the normal parsing and evaluation of the code
that they contain. This is so that they can perform their expansion with
a complete inputs. Roughly, the algorithm executing a macro follows is:

1. Macro start, pause or skip normal parsing
2. Gather macro inputs as strings
3. Evaluate macro with inputs
4. Resume normal parsing and execution.

Is this metaprogramming? You betcha!

When and where are macros used?
===============================
Macros are a practicality-beats-purity feature of many programing
languages. Because they allow you break out of the normal parsing
cycle, depending on the language, you acn do some truly wild things with
them. However, macros are really there to reduce the amount of boiler plate
code that users and developers have to write.

In C and C++ (and Fortran), the C Preprocessor ``cpp`` is a macro evaluation
engine. For example, every time you see an ``#include`` or ``#ifdef``, this is
the ``cpp`` macro system in action.
In these languages, the macros are technically outside of the definition
of the language at hand. Furthermore, because ``cpp`` must function with only
a single pass through the code, the sorts of macros that can be written with
``cpp`` are relatively simple.

Rust, on the other hand, has a first-class notion of macros that look and
feel a lot like normal functions. Macros in Rust are capable of pulling off
type information from their arguments and preventing their return values
from being consumed.

Other languages like Lisp, Forth, and Julia also provide thier macro systems.
Even restructured text (rST) directives could be considered macros.
Haskell and other more purely functional languages do not need macros (since
evaluation is lazy anyway), and so do not have them.

If these seem unfamiliar to the Python world, note that Jupyter and IPython
magics ``%`` and ``%%`` are macros!

Function Macros
===============
Xonsh supports Rust-like macros that are based on normal Python callables.
Macros do not require a special definition in xonsh. However, like in Rust,
they must be called with an exclamation point ``!`` between the callable
and the opening parentheses ``(``. Macro arguments are split on the top-level
commas ``,``, like normal Python functions.  For example, say we have the
functions ``f`` and ``g``. We could perform a macro call on these functions
with the following:

.. code-block:: xonsh

    # No macro args
    f!()

    # Single arg
    f!(x)
    g!([y, 43, 44])

    # Two args
    f!(x, x + 42)
    g!([y, 43, 44], f!(z))

Not so bad, right?  So what actually happens when to the arguments when used
in a macro call?  Well, that depends onthe defintion of the function. In
particular, each argument in the macro call is matched up with the cooresponding
parameter annotation in the callable's signature.  For example, say we have
an ``identity()`` function that is annotates its sole argument as a string:

.. code-block:: xonsh

    def identity(x : str):
        return x

If we call this normally, we'll just get whatever object we put in back out,
even if that object is not a string:

.. code-block:: xonshcon

    >>> identity('me')
    'me'

    >>> identity(42)
    42

    >>> identity(identity)
    <function __main__.identity>

However, if we perform macro calls instead we are now gauranteed to get a
the string of the source code that is in the macro call:

.. code-block:: xonshcon

    >>> identity!('me')
    "'me'"

    >>> identity!(42)
    '42'

    >>> identity!(identity)
    'identity'

Also note that each macro argument is stripped prior to passing it to the
macro itself. This is done for consistency.

.. code-block:: xonshcon

    >>> identity!(42)
    '42'

    >>> identity!(  42 )
    '42'

Importantly, because we are capturing and not evaluating the source code,
a macro call can contain input that is beyond the usual syntax. In fact, that
is sort of the whole point. Here are some cases to start your gears turning:

.. code-block:: xonshcon

    >>> identity!(import os)
    'import os'

    >>> identity!(if True:
    >>>     pass)
    'if True:\n    pass'

    >>> identity!(std::vector<std::string> x = {"yoo", "hoo"})
    'std::vector<std::string> x = {"yoo", "hoo"}'

You do you, ``identity()``.

Calling Function Macros
=======================
There are a couple of points to consider when calling macros. The first is
that passing in arguments by name will not behave as expected. This is because
the ``<name>=`` is captured by the macro itself. Using the ``identity()``
function from above:

.. code-block:: xonshcon

    >>> identity!(x=42)
    'x=42'

Performing a macro call uses only argument order to pass in values.

Additionally, macro calls split arguments only on the top-level commas.
The top-level commas are not included in any argument.
This behaves analogously to normal Python function calls. For instance,
say we have the following ``g()`` function that accepts two arguments:

.. code-block:: xonsh

    def g(x : str, y : str):
        print('x = ' + repr(x))
        print('y = ' + repr(y))

Then you can see the splitting and stripping behaviour on each macro
argument:

.. code-block:: xonshcon

    >>> g!(42, 65)
    x = '42'
    y = '65'

    >>> g!(42, 65,)
    x = '42'
    y = '65'

    >>> g!( 42, 65, )
    x = '42'
    y = '65'

    >>> g!(['x', 'y'], {1: 1, 2: 3})
    x = "['x', 'y']"
    y = '{1: 1, 2: 3}'

Hopefully, now you see the big picture.

Writing Function Macros
=======================
Though any function (or callable) can be used as a macro, this functionality
is probably most useful if the function was *designed* as a macro. There
are two aspects

globals, locals
