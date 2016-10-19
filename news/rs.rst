**Added:**

* New subprocess specification class ``SubprocSpec`` is used for specifiying
  and manipulating subprocess classes prior to execution.
* New ``PopenThread`` class runs subprocesses on a a separate thread.
* New ``CommandPipeline`` and ``HiddenCommandPipeline`` classes manage the
  execution of a pipeline of commands via the execution of the last command
  in the pipeline. Instances may be iterated and stream lines from the
  stdout buffer.
* ``$XONSH_STORE_STDOUT`` is now available on all platforms!
* The ``CommandsCache`` now has the ability to predict whether or not a
  command must be run in the foreground using ``Popen`` or may use a
  background thread and can use ``PopenThread``.
* Callable aliases may now use the full gamut of functions signatures:
  ``f()``, ``f(args)``,  ``f(args, stdin=None)``,
  ``f(args, stdin=None, stdout=None)``, and `
  ``f(args, stdin=None, stdout=None, stderr=None)``.
* Uncaptured subprocesses now recieve a PTY file handle for stdout and
  stderr.
* New ``$XONSH_PROC_FREQUENCY`` environment variable that specifies how long
  loops in the subprocess framwork should sleep. This may be adjusted from
  its default value to improved perfromance and mitigate "leaky" pipes on
  slower machines.

**Changed:**

* The ``run_subproc()`` function has been replaced with a new implementation.
* Piping between processes now uses OS pipes.
* ``$XONSH_STORE_STDIN`` now uses ``os.pread()`` rather than ``tee`` and a new
  file.
* The implementation of the ``foreground()`` decorator has been moved to
  ``unthreadable()``.

**Deprecated:** None

**Removed:**

* ``CompletedCommand`` and ``HiddenCompletedCommand`` classes have been removed
  in favor of ``CommandPipeline`` and ``HiddenCommandPipeline``.
* ``SimpleProcProxy`` and ``SimpleForegroundProcProxy`` have been removed
  in favor of a more general mechanism for dispatching callable aliases
  implemented in the ``ProcProxyThread``  and ``ProcProxy`` classes.

**Fixed:**

* May now Crtl-C out of an infinite loop with a subprocess, such as
  ```while True: sleep 1``.
* Fix for stdin redirects.
* Backgrounding works with ``$XONSH_STORE_STDOUT``
* Added a minimum time buffer time for command pipelines to check for
  if previous commands have executed successfully.  This is helpful
  for pipelines where the last command takes a long time to start up,
  such as GNU Parallel.

**Security:** None
