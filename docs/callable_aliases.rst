Callable Aliases
================

In xonsh, a Python function can be registered as a shell command (alias). The
function declares which arguments it needs, and xonsh fills them automatically
based on parameter names. When a function runs as an alias, xonsh redirects
``sys.stdout`` and ``sys.stderr`` inside it, making it possible to capture all
output that happens within the function — including ``print()`` calls and
subprocess commands.


Signature Parameters
--------------------

Callable aliases receive arguments matched by name. You can request any
combination of the following parameters in any order:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``args``
     - List of strings — command-line arguments passed to the alias.
   * - ``stdin``
     - File-like object for reading piped input, or ``None`` if no pipe.
   * - ``stdout``
     - File-like object for writing standard output.
   * - ``stderr``
     - File-like object for writing standard error.
   * - ``spec``
     - ``SubprocSpec`` object with details about how the command is being run.
   * - ``stack``
     - List of ``FrameInfo`` namedtuples from the call site (only computed if
       requested).
   * - ``alias_name``
     - The name under which the alias was registered.
   * - ``called_alias_name``
     - The name actually used to invoke the alias (may differ if one alias
       points to another).
   * - ``env``
     - A local environment overlay dict. Values set here shadow the global
       env during alias execution and are visible to subprocesses. Removed
       automatically when the alias exits.

You only need to declare the parameters you actually use:

.. code-block:: xonshcon

    @ @aliases.register
      def _hello():
          print('hello')

    @ hello
    hello

    @ @aliases.register
      def _upper(args, stdin=None):
          text = stdin.read() if stdin else ' '.join(args)
          print(text.upper())

    @ upper hello world
    HELLO WORLD
    @ echo quiet | upper
    QUIET

    @ @aliases.register
      def _shout(args, stdin=None, stdout=None):
          """Read stdin, write to stdout."""
          for line in stdin or []:
              stdout.write(line.upper())

    @ echo 'hello\nworld' | shout
    HELLO
    WORLD


Alias Name and Called Alias Name
--------------------------------

When one alias points to another, it can be useful to know how the alias was
invoked. The ``alias_name`` and ``called_alias_name`` parameters provide this:

.. code-block:: xonshcon

    @ @aliases.register('groot')
      def _groot(alias_name=None, called_alias_name=None):
          print(f'I am {alias_name}! You called me {called_alias_name}.')
    @ aliases['tree'] = 'groot'
    @ groot
    I am groot! You called me groot.
    @ tree
    I am groot! You called me tree.

``alias_name`` is set at registration time and never changes.
``called_alias_name`` is set at each invocation and reflects the name the user
actually typed.


Local Environment Overlay
-------------------------

The ``env`` parameter provides a local environment overlay. Values set in
``env`` shadow the global environment during alias execution — both for xonsh
``$VAR`` reads and for subprocesses. When the alias exits, the overlay is
removed and the global environment is unchanged.

Direct writes to ``$VAR`` or ``@.env`` modify the global environment as usual
and persist after the alias exits:

.. code-block:: xonshcon

    @ @aliases.register
      def _ca(env=None):
          $GLOBAL = 2
          echo GLOBAL before overlay = $GLOBAL
          env['GLOBAL'] = 1
          echo GLOBAL after overlay = $GLOBAL
          printenv GLOBAL

    @ ca
    GLOBAL before overlay = 2
    GLOBAL after overlay = 1
    1
    @ echo GLOBAL after alias = $GLOBAL
    GLOBAL after alias = 2

Inside the alias, ``$GLOBAL`` returns ``1`` (overlay has priority) and
subprocesses see ``GLOBAL=1`` in their environment. After the alias exits,
``$GLOBAL`` is back to ``2`` (the global value set by ``$GLOBAL = 2``).


Return Command Aliases
----------------------

The ``@aliases.return_command`` decorator creates aliases that return a new
command to execute instead of running it themselves. The ``env`` overlay works
here too — values set in ``env`` are passed to the returned command's
environment:

.. code-block:: xonshcon

    @ @aliases.register
      @aliases.return_command
      def _rca(args, env=None):
          env['LOCAL'] = 123
          $GLOBAL = 321
          return ['bash', '-c', 'echo $LOCAL']

    @ rca
    123
    @ $LOCAL
    Unknown environment variable: $LOCAL
    @ $GLOBAL
    321

The returned command ``bash -c 'echo $LOCAL'`` sees ``LOCAL=123`` in its
process environment, but ``$LOCAL`` does not exist in the global xonsh env
after the alias exits. ``$GLOBAL = 321`` was a direct write and persists.


Return Values
-------------

Callable aliases can return values in several forms:

.. code-block:: xonshcon

    @ @aliases.register
      def _ret0():
          return 0  # integer return code (0 = success)

    @ ret0
    @ $XONSH_LAST_RETURN_CODE
    0

    @ @aliases.register
      def _ret_str():
          return 'hello from return'

    @ $(ret-str)
    'hello from return\n'

    @ @aliases.register
      def _ret_tuple():
          return ('out text', 'err text', 1)

    @ !(ret-tuple)
    err text
    CommandPipeline(returncode=1, output='out text\n', errors='err text\n')

Anything printed with ``print()`` inside the function is also captured
automatically.


Capturing and Stream Redirection
--------------------------------

Inside a callable alias, ``sys.stdout`` and ``sys.stderr`` are temporarily
replaced with the alias's own streams. The ``stdout`` and ``stderr`` function
arguments point to the **same** redirected streams. This means that
``print()`` and ``print(file=stdout)`` are equivalent — both write to the
alias's captured output, not directly to the terminal:

.. code-block:: python

    # These are all the same stream inside a callable alias:
    sys.stdout  is  stdout      # True
    sys.stderr  is  stderr      # True
    print("x")                  # goes to alias stdout
    print("x", file=stdout)    # same
    stdout.write("x\n")        # same

.. code-block:: xonshcon

    @ @aliases.register
      def _demo(args, stdout=None, stderr=None):
          print("via print()")
          stdout.write("via stdout.write()\n")
          echo "via subprocess"
          print("error", file=stderr)

    @ output = $(_demo)
    error
    @ print(output)
    via print()
    via stdout.write()
    via subprocess

Here is a more complete example showing how different output methods behave
under capture:

.. code-block:: xonshcon

    @ @aliases.register
      def _printer(args, stdin, stdout, stderr):
          """Ultimate printer."""
          print("print out")
          print("print err", file=@.imp.sys.stderr)

          print("print out alias stdout", file=stdout)
          print("print err alias stderr", file=stderr)

          echo @("echo out")
          echo @("echo err") o>e

          $(echo @("$() echo out"))
          $(echo @("$() echo err") o>e)

          !(echo @("!() echo out"))
          !(echo @("!() echo err") o>e)

          ![echo @("![] echo out")]
          ![echo @("![] echo err") o>e]

          $[echo @("$[] echo out")]
          $[echo @("$[] echo err") o>e]

          execx('echo "execx echo out"')
          execx('echo "execx echo err" o>e')

    @ $(printer)
    print err
    print err alias stderr
    echo err
    $() echo err
    ![] echo err
    $[] echo out
    $[] echo err
    execx echo err
    'print out\necho out\nprint out alias stdout\n![] echo out\nexecx echo out\n'

    @ !(printer)
    $() echo err
    $[] echo out
    $[] echo err
    CommandPipeline(
      returncode=0,
      output='print out\necho out\nprint out alias stdout\n![] echo out\nexecx echo out\n',
      errors='print err\necho err\nprint err alias stderr\n![] echo err\nexecx echo err\n'
    )

When the alias is captured with ``$()`` or ``!()``, its stdout is collected.
When called uncaptured (bare command), output goes to the terminal as usual.
The ``stderr`` argument and ``sys.stderr`` are also redirected — use
``sys.__stderr__`` if you need to bypass capture:

.. code-block:: xonshcon

    @ @aliases.register
      def _loud(args, stdin=None):
          print("this is captured")
          print("this goes to real terminal", file=@.imp.sys.__stderr__)

    @ output = $(_loud)
    this goes to real terminal
    @ print(output)
    this is captured


Threading
---------

By default, callable aliases run in a **separate thread** so they can be
used in pipelines and run in the background. This is usually what you want.

However, some aliases need to run on the **main thread** — for example,
interactive tools (vim, less, htop), debuggers, profilers, or anything that
modifies terminal state. Use the
``unthreadable`` decorator to force foreground execution.

Threading and capturability can also be controlled at call time using the
``@thread``, ``@unthread`` command decorators. These override the function's
decorators for a single invocation:

.. code-block:: xonshcon

    @ @unthread my-alias    # force main thread for this call
    @ @thread my-alias      # force background thread for this call

To set it permanently on the function, use the Python decorator:

.. code-block:: xonshcon

    @ from xonsh.tools import unthreadable
    @ @aliases.register
      @unthreadable
      def _vi(args, stdin=None):
          vim @(args)

    @ vi myfile.txt
    # opens vim on the main thread


Capturability
-------------

By default, callable aliases are **capturable** — their output can be collected
with ``$()``, ``!()``, or piped to another command. This is how most aliases
work.

Some aliases launch interactive programs (editors, pagers, TUI apps) that
take over the terminal. These must not be captured, or the program will not
display correctly. Use the ``uncapturable`` decorator, typically together with
``unthreadable``:

.. code-block:: xonshcon

    @ from xonsh.tools import unthreadable, uncapturable
    @ @aliases.register
      @uncapturable
      @unthreadable
      def _edit(args, stdin=None):
          vim @(args)

    @ edit myfile.txt
    # opens vim directly in the terminal

Summary of default behavior:

.. list-table::
   :header-rows: 1

   * - Property
     - Default
     - Decorator to change
   * - Threading
     - Threaded (runs in background thread)
     - ``@unthreadable`` — run on main thread
   * - Capturing
     - Capturable (output can be collected)
     - ``@uncapturable`` — output goes to terminal only
