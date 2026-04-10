# Xonsh

Xonsh is the most modern and flexible shell available today. It combines a full-featured command language with full Python power in a single, unified environment. Everything is Python — the configuration, the scripting, the interactive experience — and at the same time it is a capable interactive shell with rich subprocess support.

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

## Development Discipline

Before making changes, research the surrounding code thoroughly — understand how the module works, what calls it, and what it depends on. Xonsh is a concurrent, multi-process environment, so pay close attention to:

- **Thread safety** — many subsystems run on background threads (syntax highlighting, completion, parser loading). Shared state must be protected
- **File descriptor leaks** — subprocess pipelines, redirects, and process proxies open fds that must be closed on every code path, including errors
- **Race conditions** — prompt rendering, command caching, and lazy initialization can overlap. Verify that concurrent access is handled correctly

Every change must be accompanied by tests.

## Code Style

- **Deprecated syntax**: The `${...}` syntax for dynamic environment variable lookup is deprecated. Never use it or mention it in code, docs, or examples. We use `@.env`.
- **Formatter/linter**: ruff (line length 88, rules: B, D, E, F, I, T10, TID, YTT, W, UP)
- **Type checking**: mypy
- **Docstrings**: NumPy convention
- **Imports**: absolute only. First-party: `xonsh`, `xontrib`, `xompletions`, `tests`
- **Commit messages**: conventional commits (`feat:`, `fix:`, `docs:`, `ci:`, etc.)
- **Pre-commit hooks**: ruff lint + ruff format + mypy + trailing-whitespace + check-yaml/toml

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
