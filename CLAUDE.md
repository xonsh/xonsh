# Xonsh

Xonsh is the most modern and flexible shell available today. It provides a full-featured command language with full Python power in a single, unified environment. Everything is Python — the configuration, the scripting, the interactive experience — and at the same time it is a capable interactive shell with rich subprocess support.

## Quick Reference

```bash
# Install for development
pip install -e '.[dev]'

# Run tests
python -m pytest                              # all tests
python -m pytest tests/test_aliases.py        # one file
python -m pytest tests/test_aliases.py -k test_cd  # one test
python -m xonsh run-tests.xsh test            # via xonsh runner

# Lint & format
ruff check . --fix
ruff format xonsh xontrib tests xompletions

# Type check
mypy

# Pre-commit (runs ruff + mypy + standard checks)
pre-commit run --all-files

# Try changes interactively
python -m xonsh --no-rc
```

## Architecture

The codebase is well-structured with clear separation of concerns — each subsystem (parsing, execution, completion, prompts, history) lives in its own module with a well-defined responsibility.

### Core Execution Flow

1. **Entry point** `xonsh.main:main()` — initializes session, loads rc files, starts shell loop
2. **XonshSession** (`xonsh/built_ins.py`) — central session object holding `env`, `execer`, `history`, `shell`, `ctx`. Accessible globally as `XSH`
3. **Execer** (`xonsh/execer.py`) — parses and executes xonsh code in two phases: context-free parsing with fallback, then context-aware AST transformation
4. **Shell** (`xonsh/shell.py`) — interactive loop. Shell types: `prompt_toolkit` (default "best"), `readline`, `dumb`, `random`

### Parser System

The parser is PLY-based (Python Lex-Yacc) with version-specific subclasses for each supported Python generation:

```
BaseParser (xonsh/parsers/base.py, ~3800 lines)
  └── v36 → v38 → v39 → v310 → v313
```

`xonsh/parser.py` selects the appropriate parser class based on `PYTHON_VERSION_INFO`. An alternative recursive-descent parser can be enabled via `XONSH_RD_PARSER` env var.

Key parser components:
- `xonsh/parsers/base.py` — grammar rules (`p_*` methods), AST node construction, `YaccLoader` thread for lazy initialization
- `xonsh/parsers/lexer.py` — hybrid tokenize/PLY lexer. Handles xonsh-specific tokens: `@$`, `??`, `@()`, `$()`, `!()`, `$[]`, `![]`, IO redirects, f-strings
- `xonsh/parsers/ast.py` — AST utilities, `CtxAwareTransformer`
- `xonsh/parsers/completion_context.py` — context parsing for tab completion
- `xonsh/parsers/fstring_adaptor.py`, `fstring_rules_llm.py` — f-string handling
- `xonsh/parsers/ply/` — embedded PLY library (vendored)

Parser tables are generated files (`parser*_table.py`, `completion_parser_table.py`) — excluded from linting and not committed.

### Subprocess System (`xonsh/procs/`)

- `specs.py` — subprocess specification, shebang parsing, binary detection
- `pipelines.py` — `CommandPipeline` / `HiddenCommandPipeline`, thread-safe execution, signal handling
- `jobs.py` — job control (`jobs`, `fg`, `bg`, `disown`)
- `proxies.py` — process proxy objects for callable aliases
- `posix.py` — platform-specific process handling

### Environment (`xonsh/environ.py`)

`Env` extends `ChainMap`. Manages all xonsh environment variables with type validators, converters, and default values. Key variable families: `XONSH_*`, `PATH`, `PROMPT`, `COMPLETIONS_*`, `HISTCONTROL`, `COLOR_*`.

### Key Modules

| Module | Purpose |
|--------|---------|
| `xonsh/aliases.py` | Alias management, `FuncAlias` for callable aliases, built-in aliases (cd, dirs, jobs, etc.) |
| `xonsh/commands_cache.py` | Caches available commands on `$PATH`, predicts threadability |
| `xonsh/completers/` | Tab completion system — Python, paths, commands, man pages, imports, environment |
| `xonsh/prompt/` | Prompt formatting — cwd, git status, virtualenv, job info, timing |
| `xonsh/history/` | History backends: JSON file, SQLite, dummy (in-memory) |
| `xonsh/shells/` | Shell implementations: prompt_toolkit, readline, dumb |
| `xonsh/pyghooks.py` | Pygments integration for syntax highlighting |
| `xonsh/tools.py` | Shared utility functions (~2800 lines) |
| `xonsh/platform.py` | Platform detection and cross-platform abstractions |
| `xonsh/xontribs.py` | Xontrib discovery, loading, management |
| `xonsh/lib/lazyasd.py` | `@lazyobject`, `LazyDict`, `LazyBool` — pervasive lazy evaluation pattern |

### Xontrib System

Xontribs (xonsh contributions) are the extension mechanism. Discovered via Python entry points (`xontrib.*`). Each xontrib is a Python module that gets loaded into the session. Built-in xontribs live in `/xontrib/`, completions in `/xompletions/`.

Key API: `xontribs load <name>`, `xontribs list`, auto-loading via `XONSH_LOAD_XONTRIBS`.

### Event System (`xonsh/events.py`)

Event-driven architecture with handler registration via decorators. Core events:
- `on_transform_command` — transform input before execution
- `on_precommand` / `on_postcommand` — before/after command execution
- `on_command_not_found` — handle unknown commands
- `on_pre_prompt_format` / `on_pre_prompt` / `on_post_prompt` — prompt lifecycle
- `on_chdir` — directory change
- `on_exit` — session teardown

## Design Patterns

The project follows consistent, well-organized patterns throughout the codebase — navigating and extending it is straightforward.

- **Lazy initialization** — `@lazyobject` decorator used extensively for expensive objects (parser, event system, platform detection). Parser tables are loaded in a background thread (`YaccLoader`)
- **Context-aware parsing** — two-phase: first parse as Python, fallback to subprocess mode. Then AST transformation based on execution context
- **Session singleton** — `XSH` global provides access to session state from anywhere
- **Inheritance chain for parsers** — each Python version extends the previous, adding new syntax rules (walrus operator, match/case, etc.)
- **Entry point plugins** — xontribs, pygments lexers, virtualenv activator, pytest plugin all discovered via entry points

## Testing

**Framework:** pytest 7+

**Style:** flat, procedural — tests are standalone functions, never grouped into classes. Use `pytest.mark.parametrize` for variations.

**LLM-generated tests:** when Claude creates a substantial block of tests for a feature or module, place them in a `test_<topic>_llm.py` file (e.g. `tests/parsers/test_parser_fstring_llm.py`). This keeps generated tests separate from hand-written ones.

**Key fixtures** (from `xonsh/pytest/plugin.py`):
- `xession` — mocked xonsh session (most commonly used)
- `xonsh_session` — full XonshSession without mocks
- `xonsh_execer` — Execer instance with event hooks
- `xonsh_execer_exec` / `xonsh_execer_parse` — factories for executing/parsing code
- `env` — mutable environment copy with temp dirs
- `xsh_with_aliases` — session with default aliases loaded
- `ptk_shell` / `readline_shell` — shell instances for interactive testing
- `check_completer` — helper for testing completions
- `load_xontrib` — dynamic xontrib loading with cleanup

**Parser test fixtures** (`tests/parsers/conftest.py`):
- `parser` — parser instance (module-scoped)
- `check_ast` / `check_stmts` / `check_xonsh_ast` — AST validation factories

**Utilities** (`xonsh/pytest/tools.py`):
- `nodes_equal()` — compare AST nodes
- `skip_if_on_windows`, `skip_if_on_conda`, `skip_if_not_has(exe)` — conditional skips

Xonsh also supports `.xsh` test files — collected via custom `XshFile`/`XshFunction` pytest hooks.

**Test dependencies**: pytest-mock, pytest-timeout, pytest-subprocess, pytest-rerunfailures, pytest-cov, pyte (terminal emulation), virtualenv

### Integration tests — invoking Python and xonsh subprocesses

Integration tests under `tests/xintegration/` (and stress / shebang tests under `tests/xoreutils/`, `tests/api/`, etc.) spawn real subprocesses. The host they run on is *not* guaranteed to have a bare `python` or `xonsh` on `$PATH` — FreeBSD ports / poudriere build jails ship only `python3.11`, slim Linux containers strip `python` and the `xonsh` console script, fresh venvs may not register the launcher. The rules below keep these tests portable.

1. **For Python: use `sys.executable`, never the literal `"python"` (or `"python3"`).** Bake it into f-strings inside scripts the test sends to xonsh and into `subprocess.run([…])` lists the test runs directly. The bare name resolves at PATH lookup time, in the *child* process — by then it's far too late to debug, and the failure shows up as a confusing `xonsh: command not found: 'python'` or `TypeError: expected str, bytes or os.PathLike object, not NoneType` from deep in `subprocess._execute_child`.

   ```python
   import sys
   # Good — explicit interpreter, works on any install layout
   script = f"$({sys.executable} -c 'print(\"tree\")')"
   sp.run([sys.executable, "-c", "import os; ..."])

   # Bad — relies on a PATH-resolvable launcher
   script = "$(python -c 'print(\"tree\")')"
   sp.run(["python", "-c", "..."])
   ```

2. **For xonsh: use `[sys.executable, "-m", "xonsh"]`, never the literal `"xonsh"` binary.** Same reasoning, plus xonsh's console-script entry point is sometimes absent (editable installs without `pip install -e .`, or `python -m xonsh` invocations on hosts without the wrapper). Helpers like `tests/xintegration/conftest.py::run_xonsh` already default to this — when extending them or writing scripts that re-invoke xonsh recursively (e.g. for ``xonsh --no-rc -c '…'`` inside an embedded test script), spell it out the same way.

   ```python
   # Good
   stdin_cmd = f"{sys.executable} -m xonsh --no-rc -c 'echo $SHLVL'"

   # Bad — fails in any environment where the `xonsh` launcher isn't on PATH
   stdin_cmd = "xonsh --no-rc -c 'echo $SHLVL'"
   ```

   The xonsh parser already does this for `(...)` subshells (see `xonsh/parsers/base.py::p_subproc_atoms_subshell`); follow the same convention in tests.

3. **Helper scripts under `tests/bin/` come from `tests/bin/templates/`.** A hardcoded shebang like `#!/usr/bin/env python3` or `#!/usr/bin/env xonsh` would fail in the same minimal environments described above. The top-level `conftest.py` reads each file in `tests/bin/templates/` at module-load time and writes the rendered script into `tests/bin/<name>`, prepending a shebang that points at the active pytest interpreter:

   - Plain Python scripts (`cat`, `wc`, `pwd`, …) get `#!{sys.executable}`.
   - xonsh scripts (`*.xsh`) get `#!/usr/bin/env -S {sys.executable} -m xonsh` — `env -S` splits the multi-arg shebang on Linux/FreeBSD/macOS 10.15+ so xonsh runs as a Python module, with no dependency on the `xonsh` console script being on `$PATH`.

   When adding a new helper script, put the body (no shebang) in `tests/bin/templates/<name>`, and add `<name>` to `tests/bin/.gitignore`. The rendered file is regenerated on every pytest invocation, including narrow ones like `pytest tests/foo.py::test_bar`. Never commit a rendered `tests/bin/<name>` — the template is the source of truth.

### Running tests in a FreeBSD poudriere jail

The xonsh FreeBSD port is built and tested by the maintainer inside a poudriere jail — a clean, reproducible chroot tied to a specific FreeBSD release. Reproducing that environment locally lets you verify port-relevant fixes (PATH, shebangs, missing `python3` symlink, `os.read` on pipe writers, etc.) before sending a patch upstream. The recipe below targets `15.0-RELEASE` because that's the maintainer's current target; bump the version as needed.

All commands run on a FreeBSD host (the steps inside the jail are tagged).

```sh
# --- 1) Host: install poudriere (one-time) -----------------------------------
sudo pkg install -y poudriere git

# --- 2) Host: minimal /usr/local/etc/poudriere.conf (one-time) ---------------
sudo tee /usr/local/etc/poudriere.conf > /dev/null <<'EOF'
NO_ZFS=yes
FREEBSD_HOST=https://download.freebsd.org
BASEFS=/usr/local/poudriere
USE_TMPFS=yes
RESOLV_CONF=/etc/resolv.conf
EOF

# --- 3) Host: create a 15.0-RELEASE jail and a ports tree (one-time) ---------
sudo poudriere jail -c -j r150 -v 15.0-RELEASE -a "$(uname -p)"
sudo poudriere ports -c -p default

# --- 4) Host: start the jail and bind-mount the source tree ------------------
sudo poudriere jail -s -j r150 -p default
JAIL_NAME=$(sudo jls -h name | awk '/r150/ {print $1; exit}')
JAIL_ROOT=/usr/local/poudriere/data/.m/${JAIL_NAME}/ref
sudo mkdir -p "${JAIL_ROOT}/home/xonsh"
sudo mount_nullfs ~/xonsh "${JAIL_ROOT}/home/xonsh"

# --- 5) Jail: install Python 3.11 and run the test suite ---------------------
sudo jexec "${JAIL_NAME}" sh -c '
    pkg install -y python311 py311-pip
    cd /home/xonsh
    python3.11 -m pip install --break-system-packages -e ".[dev]"
    python3.11 -m pytest --timeout=120
'

# --- 6) Host: tear the jail down when finished -------------------------------
sudo umount "${JAIL_ROOT}/home/xonsh"
sudo poudriere jail -k -j r150 -p default
```

Notes:

- The jail name printed by `jls` is something like `r150-default`; the `awk` line picks the first match.
- `mount_nullfs` is FreeBSD's bind-mount equivalent — changes inside the jail are reflected back in the host source tree, so you can iterate on a fix without copying files in and out. Always `umount` before `poudriere jail -k`.
- `--break-system-packages` is needed because Python 3.11 from pkg is marked PEP 668 externally-managed; the jail is throwaway, so it's safe.
- The maintainer's actual port build (`SHEBANG_FILES=` in the port Makefile) is not exercised here — this just runs the test suite under the same FreeBSD/Python combination the port targets. Port-build issues need to be reproduced with `poudriere testport -j r150 -p default -o shells/xonsh` instead.

## Development Discipline

Before making changes, research the surrounding code thoroughly — understand how the module works, what calls it, and what it depends on. Xonsh is a concurrent, multi-process environment, so pay close attention to:

- **Thread safety** — many subsystems run on background threads (syntax highlighting, completion, parser loading). Shared state must be protected
- **File descriptor leaks** — subprocess pipelines, redirects, and process proxies open fds that must be closed on every code path, including errors
- **Race conditions** — prompt rendering, command caching, and lazy initialization can overlap. Verify that concurrent access is handled correctly

Every change must be accompanied by tests.

- **Displaying messages from UI components** — completers, prompt formatters, and other interactive subsystems must use `xonsh.tools.print_above_prompt()` to display errors and diagnostics. Plain `print()` or `sys.stderr.write()` corrupts the prompt-toolkit display. `print_above_prompt` injects text above the current prompt line without breaking the terminal state.

- **Naming: completer, not completion** — the module that provides tab-completion for a command is called a **completer** (like **parser**), not a "completion". Use "completer" in module names, class names, variable names, and documentation.

## Code Style

- **Formatter/linter**: ruff (line length 88, rules: B, D, E, F, I, T10, TID, YTT, W, UP)
- **Type checking**: mypy
- **Docstrings**: NumPy convention
- **Imports**: absolute only. First-party: `xonsh`, `xontrib`, `xompletions`, `tests`
- **Commit messages**: conventional commits (`feat:`, `fix:`, `docs:`, `ci:`, etc.)
- **Pre-commit hooks**: ruff lint + ruff format + mypy + trailing-whitespace + check-yaml/toml

### Xonsh (xsh) Code Preferences

When writing xonsh code — in `.xsh` files, rc files, xontribs, docs, and examples — prefer the idiomatic xonsh form over the Python-style equivalent. These patterns are shorter, more readable, and showcase what xonsh offers.

1. **Environment lookup** — use `@.env` (attribute-style) instead of the deprecated `${...}` syntax. `${...}` must never appear in code, docs, or examples.

   ```xsh
   # Good
   echo @.env.HOME

   # Bad — deprecated
   echo ${...}['HOME']
   ```

2. **Alias registration** — prefer the `@aliases.register` decorator over dict assignment for callable aliases. The decorator keeps the name next to the function and enables richer metadata.

   ```xsh
   # Good
   @aliases.register
   def _my_cmd(args):
       ...

   # Less idiomatic
   def _my_cmd(args):
       ...
   aliases['my-cmd'] = _my_cmd
   ```

3. **One-shot env overrides** — for short commands, use the `$VAR=value cmd` prefix (with the leading `$`) instead of a `with @.env.swap(...)` block. Reserve `swap()` for multi-statement scopes.

   ```xsh
   # Good — short, inline
   $LANG='C' $LC_ALL='C' sort file.txt

   # Heavier — only when wrapping multiple statements
   with @.env.swap(LANG='C', LC_ALL='C'):
       sort file.txt
       uniq file.txt
   ```

4. **Bulk alias definition** — use the `|=` merge operator with a dict literal rather than a series of individual assignments.

   ```xsh
   # Good
   aliases |= {
       'a': 'echo a',
       'b': 'echo b',
   }

   # Noisier
   aliases['a'] = 'echo a'
   aliases['b'] = 'echo b'
   ```

5. **One-off module access** — for a single call, use implicit import via `@.imp.<module>.<func>()` instead of adding an `import` statement. Keep real `import` statements for modules used repeatedly.

   ```xsh
   # Good — single use
   pw = @.imp.getpass.getpass('password: ')

   # Use a real import only when the module is used several times
   import getpass
   pw1 = getpass.getpass('a: ')
   pw2 = getpass.getpass('b: ')
   ```

6. **Iterating over files** — use a xonsh globbing form (`` g`...` ``, `` r`...` ``, `` p`...` ``) instead of parsing `$(ls)`. Globs return lists directly, skip the subprocess, and don't break on filenames with spaces or newlines.

   ```xsh
   # Good
   for f in g`*.py`:
       echo @(f)

   # Regex glob / pathlib glob when you need them
   for f in r`.*\.log`:
       ...
   for p in p`**/*.txt`:
       print(p.stat().st_size)

   # Bad — fragile, spawns a subprocess, breaks on whitespace
   for f in $(ls).split():
       ...
   ```

7. **Installing shell-facing packages** — use `xpip` instead of `pip` when the package is for xonsh itself (xontribs, completers, libraries you'll use from the shell or rc files). `xpip` targets the Python interpreter running xonsh, which matters when xonsh is installed in an isolated env (conda, mamba, homebrew, AppImage) and a bare `pip` would install into the wrong interpreter. Use plain `pip` only when you're working inside a project's own virtualenv.

   ```xsh
   # Good — installs into the xonsh interpreter
   xpip install xontrib-vox

   # Plain pip is fine only when a project venv is active
   pip install -e .
   ```

8. **One-off output format** — for a single capture, use a command decorator inside `$(...)` (`@lines`, `@json`, `@jsonl`, `@yaml`, `@paths`, …) instead of flipping `$XONSH_SUBPROC_OUTPUT_FORMAT` globally. Reserve the env var for session-wide defaults.

   ```xsh
   # Good — scoped to this call
   procs = $(@lines ps -ax)
   data = $(@json curl -s https://example.com/data.json)

   # Avoid for one-off use — leaks into every later capture
   $XONSH_SUBPROC_OUTPUT_FORMAT = 'list_lines'
   procs = $(ps -ax)
   ```

9. **Modules as classes** — when a module (xontrib, rc helper, integration) has more than one related function, group them as methods on a class and instantiate once, rather than exposing a flat list of prefixed functions. Classes keep related state together, avoid name-prefix noise, and give users a natural dot-path to explore via tab completion.

   ```xsh
   # Good — cohesive namespace, tab-completable
   class MyIntegration:
       def func1(self): ...
       def func2(self): ...

   my = MyIntegration()
   my.func1()
   my.func2()

   # Less ideal — prefix-based namespacing, no shared state
   def myint_func1(): ...
   def myint_func2(): ...
   ```

10. **Non-trivial integrations as session attributes** — when building a sizeable integration or piece of complex functionality (e.g. VSCode, Docker, a remote API), take the class from point 9 one step further and attach the instance to the session via `@.<name> = <Class>()`. This gives the user a discoverable, namespaced handle (`@.vscode.any_tuning()`) reachable from anywhere in the session, rc files, or other xontribs.

    ```xsh
    # Good — one explicit entry point, methods hang off the class
    class VSCodeIntegration:
        def open(self, path): ...
        def any_tuning(self): ...

    @.vscode = VSCodeIntegration()

    # Later, anywhere in the session / rc / xontrib
    @.vscode.open('.')
    @.vscode.any_tuning()
    ```

    Reach for this when the integration has state, several related operations, or needs to expose a small API to the user. For a single helper function, a plain alias or callable is still fine.

11. **Environment variable naming** — new environment variables must follow the pattern `$XONSH_<COMPONENT>_<SETTING>`, e.g. `$XONSH_COMMANDS_CACHE_TRACE`, `$XONSH_HISTORY_SIZE`. Not all existing variables follow this convention yet — they will be renamed over time — but every newly added variable must use it.

12. **Working with LLMs — research first, code second** — when using an LLM to change this codebase, first ask it to investigate the code it's about to touch: read the relevant module, search for every caller, map the surrounding invariants, and return a written plan of the proposed changes. Only after you've reviewed that plan should you let it implement. Skipping the research step — the "I want to fix this, just do it" prompt — pushes the model toward the shortest patch that compiles, which routinely breaks callers, skips edge cases, and produces integration bugs. Xonsh is a concurrent, multi-process system with many subtle interactions (parser, procs, events, prompt, completion), so a change that looks local often isn't. Don't skip the plan.

### Documentation Preferences

1. **Linking the xonsh RC file in docs** — in `.rst` files, instead of bare `~/.xonshrc`, `.xonshrc`, or an inline `xonshrc` code span, write the phrase **xonsh RC** and render it as a link to `xonshrc.rst` via `:doc:`xonsh RC <xonshrc>``. This gives a uniform, readable hyperlink to the RC-file guide and avoids mixing the path, the filename, and the concept. If the mention has to appear inside a `code-block::` (where Sphinx roles don't render), lift it into the surrounding prose and keep the code sample itself free of that filename.

   ```rst
   # Good
   Add this snippet to your :doc:`xonsh RC <xonshrc>`:

   .. code-block:: xonsh

       $XONSH_DEBUG_BREAKPOINT_ENGINE = 'pdbp'

   # Bad — bare filename, no link
   Add this snippet to your ``~/.xonshrc``:

   .. code-block:: xonsh

       # In ~/.xonshrc
       $XONSH_DEBUG_BREAKPOINT_ENGINE = 'pdbp'
   ```

2. **Use `@` as the xonsh prompt in examples** — whenever you show an interactive xonsh command line (typically inside ``.. code-block:: xonshcon``), prefix the command with `@ `. `@` is the default rendering of `{prompt_end}` in `$PROMPT` and xonsh's most recognizable visual cue — readers spot an `@ ` and know it's a xonsh session. Never use `$` or `>` as the prompt marker for xonsh commands: `$` reads as a bash/sh prompt, `>` as a generic REPL, and both blur the line between shells. Reserve `$` for code-blocks that genuinely show a bash/sh prompt (e.g. a system-level command run *before* xonsh starts).

   ```rst
   # Good — xonsh session, marked with @
   .. code-block:: xonshcon

       @ ls | grep py
       @ $PATH.append('/opt/bin')

   # Bad — looks like bash, ambiguous
   .. code-block:: xonshcon

       $ ls | grep py
       > $PATH.append('/opt/bin')

   # Fine — an explicitly-bash prelude
   .. code-block:: bash

       $ env LD_PRELOAD=libgcc_s.so.1 xonsh
   ```

## CI

GitHub Actions matrix: Ubuntu/macOS/Windows x Python 3.11/3.12/3.13/3.14. Tests run with 600s timeout. Coverage collected on Python 3.12. Package manager: `uv`.

## Python Version Support

Follows NEP-29: supports the 4 most recent Python minor versions. Currently 3.11 through 3.14. Each version may have its own parser subclass.

## Project Layout

```
xonsh/                  Core package
  parsers/              PLY-based parser system (base + version-specific)
    ply/                Vendored PLY library
  procs/                Subprocess and pipeline execution
  completers/           Tab completion providers
  prompt/               Prompt formatting
  history/              History backends (JSON, SQLite)
  shells/               Shell implementations (ptk, readline, dumb)
    ptk_shell/          prompt_toolkit shell
  lib/                  Utilities (lazy loading, pretty printing, inspection)
  api/                  Public API modules
  platforms/            Platform-specific code
  xoreutils/            Cross-platform coreutils (cat, uname, uptime)
  pytest/               Pytest plugin and test utilities
  webconfig/            Web-based configuration UI
  virtualenv/           Virtualenv activation support
xontrib/                Built-in xontribs
xompletions/            Completions for common tools (cd, pip, gh, python)
tests/                  Test suite
  parsers/              Parser-specific tests
docs/                   Sphinx documentation (xon.sh)
```
