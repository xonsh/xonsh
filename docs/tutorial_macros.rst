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

Function Macros
===============
Xonsh supports Rust-like macros that are based on Python callables.
