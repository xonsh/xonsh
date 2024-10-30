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

Is this meta-programming? You betcha!

When and where are macros used?
===============================
Macros are a practicality-beats-purity feature of many programming
languages. Because they allow you break out of the normal parsing
cycle, depending on the language, you can do some truly wild things with
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

Other languages like Lisp, Forth, and Julia also provide their macro systems.
Even restructured text (rST) directives could be considered macros.

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

Not so bad, right?  So what actually happens to the arguments when used
in a macro call?  Well, that depends on the definition of the function. In
particular, each argument in the macro call is matched up with the corresponding
parameter annotation in the callable's signature.  For example, say we have
an ``identity()`` function that annotates its sole argument as a string:

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

However, if we perform macro calls instead we are now guaranteed to get
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

Then you can see the splitting and stripping behavior on each macro
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

Sometimes you may only want to pass in the first few arguments as macro
arguments and you want the rest to be treated as normal Python arguments.
By convention, xonsh's macro caller will look for a lone ``*`` argument
in order to split the macro arguments and the regular arguments. So for
example:

.. code-block:: xonshcon

    >>> g!(42, *, 65)
    x = '42'
    y = 65

    >>> g!(42, *, y=65)
    x = '42'
    y = 65

In the above, note that ``x`` is still captured as a macro argument. However,
everything after the ``*``, namely ``y``, is evaluated is if it were passed
in to a normal function call.  This can be useful for large interfaces where
only a handful of args are expected as macro arguments.

Hopefully, now you see the big picture.

Writing Function Macros
=======================
Though any function (or callable) can be used as a macro, this functionality
is probably most useful if the function was *designed* as a macro. There
are two main aspects of macro design to consider: argument annotations and
call site execution context.


Macro Annotations
-----------------------------------
There are six kinds of annotations that macros are able to interpret:

.. list-table:: Kinds of Annotation
   :header-rows: 1

   * - Category
     - Object
     - Flags
     - Modes
     - Returns
   * - String
     - ``str``
     - ``'s'``, ``'str'``, or ``'string'``
     -
     - Source code of argument as string, *default*.
   * - AST
     - ``ast.AST``
     - ``'a'`` or ``'ast'``
     - ``'eval'`` (default), ``'exec'``, or ``'single'``
     - Abstract syntax tree of argument.
   * - Code
     - ``types.CodeType`` or ``compile``
     - ``'c'``, ``'code'``, or ``'compile'``
     - ``'eval'`` (default), ``'exec'``, or ``'single'``
     - Compiled code object of argument.
   * - Eval
     - ``eval`` or ``None``
     - ``'v'`` or ``'eval'``
     -
     - Evaluation of the argument.
   * - Exec
     - ``exec``
     - ``'x'`` or ``'exec'``
     - ``'exec'`` (default) or ``'single'``
     - Execs the argument and returns None.
   * - Type
     - ``type``
     - ``'t'`` or ``'type'``
     -
     - The type of the argument after it has been evaluated.

These annotations allow you to hook into whichever stage of the compilation
that you desire. It is important to note that the string form of the arguments
is split and stripped (as described above) prior to conversion to the
annotation type.

Each argument may be annotated with its own individual type. Annotations
may be provided as either objects or as the string flags seen in the above
table. String flags are case-insensitive.
If an argument does not have an annotation, ``str`` is selected.
This makes the macro function call behave like the subprocess macros and
context manager macros below. For example,

.. code-block:: xonsh

    def func(a, b : 'AST', c : compile):
        pass

In a macro call of ``func!()``,

* ``a`` will be evaluated with ``str`` since no annotation was provided,
* ``b`` will be parsed into a syntax tree node, and
* ``c`` will be compiled into code object since the builtin ``compile()``
  function was used as the annotation.

Additionally, certain kinds of annotations have different modes that
affect the parsing, compilation, and execution of its argument.  While a
sensible default is provided, you may also supply your own. This is
done by annotating with a (kind, mode) tuple.  The first element can
be any valid object or flag. The second element must be a corresponding
mode as a string.  For instance,

.. code-block:: xonsh

    def gunc(d : (exec, 'single'), e : ('c', 'exec')):
        pass

Thus in a macro call of ``gunc!()``,

* ``d`` will be exec'd in single-mode (rather than exec-mode), and
* ``e`` will be compiled in exec-mode (rather than eval-mode).

For more information on the differences between the exec, eval, and single
modes please see the Python documentation.


Macro Function Execution Context
--------------------------------
Equally important as having the macro arguments is knowing the execution
context of the macro call itself. Rather than mucking around with frames,
macros provide both the globals and locals of the call site.  These are
accessible as the ``macro_globals`` and ``macro_locals`` attributes of
the macro function itself while the macro is being executed.

For example, consider a macro which replaces all literal ``1`` digits
with the literal ``2``, evaluates the modification, and returns the results.
To eval, the macro will need to pull off its globals and locals:

.. code-block:: xonsh

    def one_to_two(x : str):
        s = x.replace('1', '2')
        glbs = one_to_two.macro_globals
        locs = one_to_two.macro_locals
        return eval(s, glbs, locs)

Running this with a few of different inputs, we see:

.. code-block:: xonshcon

    >>> one_to_two!(1 + 1)
    4

    >>> one_to_two!(11)
    22

    >>> x = 1
    >>> one_to_two!(x + 1)
    3

Of course, many other more sophisticated options are available depending on the
use case.


Subprocess Macros
=================
Like with function macros above, subprocess macros allow you to pause the parser
for until you are ready to exit subprocess mode. Unlike function macros, there
is only a single macro argument and its macro type is always a string.  This
is because it (usually) doesn't make sense to pass non-string arguments to a
command. And when it does, there is the ``@()`` syntax!

In the simplest case, subprocess macros look like the equivalent of their
function macro counterparts:

.. code-block:: xonshcon

    >>> echo! I'm Mr. Meeseeks.
    I'm Mr. Meeseeks.

Again, note that everything to the right of the ``!`` is passed down to the
``echo`` command as the final, single argument. This is space preserving,
like wrapping with quotes:

.. code-block:: xonshcon

    # normally, xonsh will split on whitespace,
    # so each argument is passed in separately
    >>> echo x  y       z
    x y z

    # usually space can be preserved with quotes
    >>> echo "x  y       z"
    x  y       z

    # however, subprocess macros will pause and then strip
    # all input after the exclamation point
    >>> echo! x  y       z
    x  y       z

However, the macro will pause everything, including path and environment variable
expansion, that might be present even with quotes.  For example:

.. code-block:: xonshcon

    # without macros, environment variable are expanded
    >>> echo $USER
    lou

    # inside of a macro, all additional munging is turned off.
    >>> echo! $USER
    $USER

Everything to the right of the exclamation point, except the leading and trailing
whitespace, is passed into the command directly as written. This allows certain
commands to function in cases where quoting or piping might be more burdensome.
The ``timeit`` command is a great example where simple syntax will often fail,
but will be easily executable as a macro:

.. code-block:: xonshcon

    # fails normally
    >>> timeit "hello mom " + "and dad"
    xonsh: subprocess mode: command not found: hello

    # macro success!
    >>> timeit! "hello mom " + "and dad"
    100000000 loops, best of 3: 8.24 ns per loop

All expressions to the left of the exclamation point are passed in normally and
are not treated as the special macro argument. This allows the mixing of
simple and complex command line arguments. For example, sometimes you might
really want to write some code in another language:

.. code-block:: xonshcon

    # don't worry, it is temporary!
    >>> bash -c ! export var=42; echo $var
    42

    # that's better!
    >>> python -c ! import os; print(os.path.abspath("/"))
    /

Compared to function macros, subprocess macros are relatively simple.
However, they can still be very expressive!

Context Manager Macros
======================
Now that we have seen what life can be like with macro expressions, it is time
to introduce the macro statement: ``with!``.  With-bang provides macros
on top of existing Python context managers. This provides both anonymous
and onymous blocks in xonsh.

The syntax for context manager macros is the same as the usual with-statement
in Python, but with an additional exclamation point between the ``with`` word
and the first context manager expression. As a simple example,

.. code-block:: xonsh

    with! x:
        y = 10
        print(y)

In the above, everything to the left of the colon (``x``) will be evaluated
normally. However, the body will not be executed and ``y`` will not be defined
or printed. In this case, the body will be attached to x as a string, along with
globals and locals, prior to the body even being entered. The body is then
replaced with a ``pass`` statement. You can think of the above as being
transformed into the following:

.. code-block:: xonsh

    x.macro_block = 'y = 10\nprint(y)\n'
    x.macro_globals = globals()
    x.macro_locals = locals()
    with! x:
        pass

There are a few important things about this to notice:

1. The ``macro_block`` string is dedented,
2. The ``macro_*`` attributes are set *before* the context manager is entered so
   the ``__enter__()`` method may use them, and
3. The ``macro_*`` attributes are not cleaned up automatically so that the
   context manager may use them even after the object is exited. The
   ``__exit__()`` method may clean up these attributes, if desired.

By default, macro blocks are returned as a string. However, like with function
macro arguments, the kind of ``macro_block`` is determined by a special
annotation.  This annotation is given via the ``__xonsh_block__`` attribute
on the context manager itself.  This allows the block to be interpreted as
an AST, byte compiled, etc.

The convenient part about this syntax is that the macro block is only
exited once it sees a dedent back to the level of the ``with!``. All other
code is indiscriminately skipped! This allows you to write blocks of code in
languages other than xonsh without pause.

For example, consider a simple
XML macro context manager. This will return the parsed XML tree from a
macro block. The context manager itself can be written as:


.. code-block:: python

    import xml.etree.ElementTree as ET

    class XmlBlock:

        # make sure the macro_block comes back as a string
        __xonsh_block__ = str

        def __enter__(self):
            # parse and return the block on entry
            root = ET.fromstring(self.macro_block)
            return root

        def __exit__(self, *exc):
            # no reason to keep these attributes around.
            del self.macro_block, self.macro_globals, self.macro_locals


The above class may then be used in a with-bang as follows:

.. code-block:: xonsh

    with! XmlBlock() as tree:
        <note>
          <to>You</to>
          <from>Xonsh</from>
          <heading>Don't You Want Me, Baby</heading>
          <body>
            You know I don't believe you when you say that you don't need me.
          </body>
        </note>

And if you run this, you'll see that the ``tree`` object really is a parsed
XML object.

.. code-block:: xonshcon

    >>> print(tree.tag)
    note


So in roughly eight lines of xonsh code, you can seamlessly interface
with another, vastly different language.

The possibilities for this are not limited to just markup languages or other
party tricks. You could be a remote execution interface via SSH, RPC,
dask / distributed, etc. The real benefit of context manager macros is
that they allow you to select when, where, and what code is executed as a
part of the xonsh language itself.

The power is there; use it without reservation!

Take Away
=========
Hopefully, at this point, you see that a few well placed macros can be extremely
convenient and valuable to any project.
