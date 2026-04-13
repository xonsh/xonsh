# Release Description

## Overview

A major release focused on reliability and language capabilities. The process subsystem has been reworked with proper thread safety, file descriptor management, and pipe handling across all platforms. The parser now supports PEP 701 f-strings, the walrus operator for env variables, and positional-only arguments. Completions are smarter — sorted by substring match position with visual highlighting. Callable aliases gained a local `env` overlay, decorator-based configuration, and full help/superhelp support. Globbing is unified under `$DOTGLOB` with a new regex match glob `m`. Over 100 potential breaking cases were identified and resolved, making this the most stable release of xonsh to date.

## Changes requiring attention

### Error handling for subprocess chains enabled by default ([#6267](https://github.com/xonsh/xonsh/issues/6267))

Xonsh now treats subprocess commands like real code. Every subprocess chain raises an exception on non-zero exit by default (`$XONSH_SUBPROC_RAISE_ERROR=True`), so a failing command in a function or loop stops execution immediately instead of silently letting subsequent logic run on invalid state:

```xsh
ls nofile                          # exception
ls nofile || echo fallback         # no exception — chain handled the error
echo ok && ls nofile ; echo done   # exception on the first chain

def func():
    echo Start
    ls nofile    # exception
    echo End
func()
# BEFORE: Start <stderr> End
# NOW: Start <stderr> <exception>
```

Captured subprocess `!()` does not raise — full control is on the user:

```xsh
if !(ls nofile):    # no exception — user handles the result
    pass
```

For granular error handling use command decorators and env swap:

```xsh
@error_ignore ls nofile                        # suppress for this command
with @.env.swap(XONSH_SUBPROC_RAISE_ERROR=False):
    ls nofile                                  # suppress for this block
!(@error_raise ls nofile)                      # raise exception
```

The old `$RAISE_SUBPROC_ERROR` (raise exception on every command) is renamed to `$XONSH_SUBPROC_CMD_RAISE_ERROR` (default `False`).

### Globbing: `$DOTGLOB` now controls all globs including regex ([#6234](https://github.com/xonsh/xonsh/issues/6234))

Previously regex globs (`` r`\..*` ``) and backtick globs always matched dotfiles regardless of `$DOTGLOB`. Now all glob forms respect it uniformly. Since `$DOTGLOB` defaults to `False`, existing scripts that use regex globs to match hidden files will stop finding them. Set `$DOTGLOB = True` if you want to match hidden files.

### Prompt: Completions match by substring, not just prefix ([#6125](https://github.com/xonsh/xonsh/issues/6125))

Typing `deploy` now finds `dev-xonsh-deploy`. Results are sorted by substring position — earlier matches rank higher.

### Process subsystem reworked ([#6159](https://github.com/xonsh/xonsh/issues/6159))

Pipe fd management, thread safety, and signal handling have been rewritten. Callable aliases in pipes are now stable. If you had workarounds for fd leaks or I/O errors in pipes — they are likely no longer needed and can be removed.


## Shining Features

### Substring completions ([#6125](https://github.com/xonsh/xonsh/issues/6125))

```xsh
aliases |= {'dev-xonsh-deploy': 'echo'}
deploy<Tab>
# dev-xonsh-deploy    # matched by substring, sorted by position
```

### PEP 701 f-strings ([#6202](https://github.com/xonsh/xonsh/issues/6202))

```xsh
echo f"{'hello':>10}"
#      hello
```

### Compile xsh xontribs and imports ([#6167](https://github.com/xonsh/xonsh/issues/6167))

```xsh
# ~/.xonshrc compiled on first load
import mymod           # mymod.xsh compiled and cached
xontrib load gitinfo   # xontrib gitinfo.xsh compiled and cached
```

### Non-blocking prompt ([#6183](https://github.com/xonsh/xonsh/issues/6183))

Syntax highlighting is now non-blocking — typing feels instant regardless of `$PATH` size. Especially noticeable
on Windows with slow directories. Slow `$PATH` directories can be cached to `$XONSH_COMMANDS_CACHE_READ_DIR_ONCE`.

### Regex glob `m` with match groups ([#6235](https://github.com/xonsh/xonsh/issues/6235))

```xsh
for parent, file in m`src/(.*)/(.*\.png)`:  # return match groups
    print(parent, file)

m`src/.*`.files().paths()  # chain processing
m`src/(.*)/(.*\.py)`.select(1).unique().sorted()  # group chain processing
```

### Help and superhelp for env vars and aliases ([#6222](https://github.com/xonsh/xonsh/issues/6222), [#6263](https://github.com/xonsh/xonsh/issues/6263))

```xsh
$PATH?     # shows variable description, type, default
$PATH??    # shows full details

my-ls?               # shows alias, resolved alias and executable path
my-callable-alias??  # shows source code and file location of callable alias
```

### Instant Click CLI integration for callable aliases ([#6265](https://github.com/xonsh/xonsh/issues/6265))

```xsh
@aliases.register_click_command
@aliases.click.option('--name', default='World')
def _hello(ctx, name):
    """Greet someone."""
    print(f'Hello {name}!', file=ctx.stdout)
    print(f'Callable alias args like stdout are availablead in ctx.', file=ctx.stdout)
    ctx.click.echo('And click too.')

hello --name Snail    # Hello Snail
hello --help          # shows usage, options, description
hello??               # shows source code and file location if it was imported
```

### Command decorators list was extended  ([#6212](https://github.com/xonsh/xonsh/issues/6212))

Added `@path`, `@paths`, `@error_ignore`, `@error_raise`.

```xsh
$(@path echo '/bin')                 # Path('/bin')
echo 1 && @error_ignore ls nonono    # no exception
```

### Emoji and symbols completion ([#6246](https://github.com/xonsh/xonsh/issues/6246))

```xsh
$XONSH_COMPLETER_EMOJI_PREFIX = "::"  # disabled by default
$XONSH_COMPLETER_SYMBOLS_PREFIX = ":::" # disabled by default

::<Tab>        # shows emoji picker: ✨
::cat<Tab>     # shows 🐈 related emoji
::<Tab>        # shows symbols picker: ⚝
:::arr<Tab>    # shows arr symbols: →, ↔, ↗.
```

### Prompt: `Tab`/`Shift-Tab` indent and `Shift+Enter` newline ([#6213](https://github.com/xonsh/xonsh/issues/6213))

IDE-like experience in the prompt: select lines of a multiline command with `Shift+Arrow`, then `Tab`/`Shift-Tab` to indent/dedent the selection. `Shift+Enter` inserts a newline without submitting.

### Cursor position for next command ([#6244](https://github.com/xonsh/xonsh/issues/6244))

```xsh
$XONSH_PROMPT_NEXT_CMD = 'echo My name is @(<edit>)'
```

### Windows script execution ([#6180](https://github.com/xonsh/xonsh/issues/6180))

```xsh
$PATHEXT = ['.xsh', '.py']
./myscript.xsh    # runs in xonsh
./myscript.py     # runs in python
./myscript        # resolved by PATHEXT
```

### Xonsh WinGet Installer on Windows

Now we have [Xonsh installer](https://github.com/xonsh/xonsh-winget/releases) for Windows.
The WinGet package for xonsh 0.23.0 will be uploaded soon.

# Release Notes

## Important changes

* **Error Handling:** Raising exceptions for subprocess chains is enabled by default. Logical operations (`||`, `&&`) are handled correctly. `$RAISE_SUBPROC_ERROR` deprecated in favor of `$XONSH_SUBPROC_CMD_RAISE_ERROR` ([#6267](https://github.com/xonsh/xonsh/issues/6267))
* **Processes:** Major improvements to core logic for threads, pipes, file descriptors, and process output management across all platforms ([#6159](https://github.com/xonsh/xonsh/issues/6159))
* **Parser:** First version with support of PEP 701 f-strings ([#6202](https://github.com/xonsh/xonsh/issues/6202)), @anki-code
* **Completer:** Order completions by both prefix and substring matches, sort by substring position. Remove `$CASE_SENSITIVE_COMPLETIONS` ([#6125](https://github.com/xonsh/xonsh/issues/6125))
* **Glob:** `$DOTGLOB` now controls all forms of globbing uniformly (normal, regex) with a dedicated documentation page ([#6234](https://github.com/xonsh/xonsh/issues/6234))
* **Performance:** Compile xsh xontribs and imports ([#6167](https://github.com/xonsh/xonsh/issues/6167))
* **Windows/WSL:** Improved execution performance and prompt highlighting with commands cache ([#6183](https://github.com/xonsh/xonsh/issues/6183))
* **Windows:** Fixed executing scripts and binary files ([#6180](https://github.com/xonsh/xonsh/issues/6180))


## Features

* **Error Handling:** Raising exceptions for subprocess chains is enabled by default. Logical operations (`||`, `&&`) are handled correctly. Captured `!()` does not raise. `@error_ignore`/`@error_raise` decorators for per-command control ([#6267](https://github.com/xonsh/xonsh/issues/6267)), @anki-code (@nbecker, @AstraLuma, @certik, @gforsyth, @melund, @scopatz, @hexagonrecursion, @carhe, @ading2210, @zhuoqun-chen, @petergaultney, @Qyriad, @buster-blue, @jmdesprez, @thelittlebug)
* **Parser:** First version with support of PEP 701 f-strings ([#6202](https://github.com/xonsh/xonsh/issues/6202)), @anki-code
* **Parser:** Added walrus operator support for env variables e.g. `echo @($TMP := '/tmp') && ls $TMP` ([#6226](https://github.com/xonsh/xonsh/issues/6226)), @anki-code
* **Parser:** Introduced python macro substitution `@!()` e.g. `echo @!(2+2)` returns the expression as a string ([#6271](https://github.com/xonsh/xonsh/issues/6271)), @anki-code (@daniel-shimon, @Qyriad, @aeshna-cyanea, @elgow, @inmaldrerah, @mtalexan, @rtomaszewski, @singpolyma)
* **Parser:** Reduce shadowing by using experimental `$XONSH_BUILTINS_TO_CMD=True` ([#6227](https://github.com/xonsh/xonsh/issues/6227)), @anki-code (@elgow, @sawolford, @bestlem, @gforsyth, @laloch, @qwenger, @scopatz)
* **Callable Alias:** Refactoring: `env` arg as local overlay, `(called_)alias_name` args. Added `@aliases.(un)(threadable/capturable)` decorators. Added distinct Callable Alias page in docs ([#6245](https://github.com/xonsh/xonsh/issues/6245)), @anki-code (@dysfungi)
* **Callable Alias:** Better help (`?`) and superhelp (`??`) for aliases and callable aliases ([#6263](https://github.com/xonsh/xonsh/issues/6263)), @anki-code
* **Callable Alias:** Added Click CLI interface support via `@aliases.register_click_command` ([#6265](https://github.com/xonsh/xonsh/issues/6265)), @anki-code (@AstraLuma, @deeuu, @halloleo, @jnoortheen, @micimize, @scopatz, @wasertech)
* **Subprocess:** Added support for subprocess substitution in the middle of a string e.g. `echo prefix_$(whoami)_suffix` ([#6166](https://github.com/xonsh/xonsh/issues/6166)), @anki-code (@xylin-dev)
* **Command Decorators:** Added `@path`, `@paths`, `@error_raise`, `@error_ignore` ([#6212](https://github.com/xonsh/xonsh/issues/6212)), @anki-code
* **CommandPipeline:** Added `pipecode` and `pipestatus` ([#6228](https://github.com/xonsh/xonsh/issues/6228)), @anki-code (@hexagonrecursion, @carhe, @Qyriad, @buster-blue, @jmdesprez, @thelittlebug)
* **Completer:** Order completions by both prefix and substring matches, sort by substring position. Remove `$CASE_SENSITIVE_COMPLETIONS` ([#6125](https://github.com/xonsh/xonsh/issues/6125)), @costajohnt (@anki-code, @wajdiJomaa, @inmaldrerah, @pewill)
* **Completer:** Underline matched substring in completion menu ([#6149](https://github.com/xonsh/xonsh/issues/6149)), @costajohnt (@anki-code)
* **Completer:** Support emoji and symbols inserting via `$XONSH_COMPLETER_EMOJI_PREFIX` and `$XONSH_COMPLETER_SYMBOLS_PREFIX` ([#6246](https://github.com/xonsh/xonsh/issues/6246)), @anki-code
* **Env:** Added help and superhelp support for env variables i.e. `$VAR?` and `$VAR??` ([#6222](https://github.com/xonsh/xonsh/issues/6222)), @anki-code (@jdjohnston)
* **Env:** Added VarPattern that provides typing by name pattern for environment variables ([#6223](https://github.com/xonsh/xonsh/issues/6223)), @anki-code (@dhhdhshdja)
* **Env:** Added `$XONSH_SUBPROC_ARG_EXPANDUSER` to switch expanding off ([#6240](https://github.com/xonsh/xonsh/issues/6240)), @anki-code (@agoose77)
* **Glob:** Added regex glob `m` that returns match groups as XonshList instead of paths e.g. `for path, file in m'(.*)/(.*)\.png': print(path, file)` ([#6235](https://github.com/xonsh/xonsh/issues/6235)), @anki-code (@yohan-pg)
* **Prompt-toolkit:** Added `Tab`/`Shift-Tab` to (de)indent selected lines. Added `Shift+Enter` to start next line ([#6213](https://github.com/xonsh/xonsh/issues/6213)), @anki-code
* **Prompt:** Ability to set cursor position for the next command via `$XONSH_PROMPT_NEXT_CMD` ([#6244](https://github.com/xonsh/xonsh/issues/6244)), @anki-code (@slacksystem)
* **Prompt:** Added `Ctrl+C` in selection mode to copy selected text ([#6247](https://github.com/xonsh/xonsh/issues/6247)), @anki-code
* **Prompt:** Support OSC7 escape sequences. Now terminal app can restore shell cwd state after reboot. (#6300) @anki-code (@coolcoder613eb)
* **Prompt:** Fixed comment highlighting in subproc mode (#5159) @anki-code (@rpdelaney, @alaestor)
* **Events:** Now on_command_not_found event supports dict with env overlay.
* **Source foreign:** Added parsing of multiline env variables ([#6253](https://github.com/xonsh/xonsh/issues/6253)), @anki-code (@agoose77)
* **Performance:** Compile xsh xontribs and imports ([#6167](https://github.com/xonsh/xonsh/issues/6167)), @anki-code (@AsafFisher, @scopatz, @micahdlamb, @aloony, @720415, @Minabsapi, @dyuri, @raddessi, @zscholl, @inmaldrerah, @jnoortheen)
* **Windows/WSL:** Improved execution performance and prompt highlighting with commands cache ([#6183](https://github.com/xonsh/xonsh/issues/6183)), @anki-code (@ndemou, @gforsyth, @scopatz, @jaraco, @KoStard, @BYK, @AsafFisher, @NotTheDr01ds, @bestlem, @daddycocoaman, @geoffreyvanwyk, @kodjac, @danielcranford, @toihr, @laloch, @melund, @DeadlySquad13, @egigoka, @panki27, @willothy)
* **Windows:** Added installation script and instructions to the installation guide ([#6196](https://github.com/xonsh/xonsh/issues/6196)), @anki-code
* **Builtins:** Added `xxonsh` - launches exactly the same xonsh that was used to start the current session. Also tmux example in the docs. ([#6283](https://github.com/xonsh/xonsh/pull/6283)), @anki-code
* **Builtins**: `xcontext` now resolves the paths before showing and highlight green if python/xpython, xonsh/xxonsh have the same real path. ([#6286)](https://github.com/xonsh/xonsh/pull/6286))
* **Xontrib:** Show xontrib description in `xontrib list` output ([#6181](https://github.com/xonsh/xonsh/issues/6181)), @knQzx (@anki-code)
* **Package:** Flatpak support. Xonsh Flatpak build in https://github.com/xonsh/xonsh-flatpak, @anki-code


## Fixes

* **Processes:** Major improvements to core logic for threads, pipes, file descriptors, and process output management across all platforms ([#6159](https://github.com/xonsh/xonsh/issues/6159)), @anki-code (@gforsyth, @jaraco, @jnoortheen, @scopatz, @AstraLuma, @Qyriad, @doronz88, @AdamJamil, @davidxmoody, @andry81, @blahgeek, @wlritchi, @Harding-Stardust, @arkhan, @mitnk, @whitelynx, @junegunn, @dev2718, @deeuu, @laloch, @beetleb, @cottrell, @ediphy-dwild, @nedsociety, @gnat, @nahoj, @andrew222651, @lambda-abstraction, @lunrenyi, @greenbech, @taw, @bestlem, @jlevy, @kokeshing, @FlyingWombat, @rosalogia, @CaremOstor, @krissik, @Techcable, @tkossak, @inmaldrerah, @Cadair, @720415, @Minabsapi, @dyuri, @raddessi, @zscholl)
* **Process:** Close only writer in case of reading from stdin in callable alias ([#6266](https://github.com/xonsh/xonsh/issues/6266)), @anki-code
* **Process:** Implement post command error handling ([b07d831](https://github.com/xonsh/xonsh/commit/b07d831cd2a00031aeca34c94c1793039cb9ae53)), @anki-code
* **Process:** Reopen stdin from /dev/tty so that child processes (e.g. fzf, vim) can interact with the terminal when xonsh reads a script from stdin ([#6274](https://github.com/xonsh/xonsh/issues/6274)), @anki-code
* **Parser:** Fix check_for_partial_string: unmatched/unclosed quotes inside `#` comments prevent the prompt from being submitted ([#6264](https://github.com/xonsh/xonsh/issues/6264)), @anki-code
* **Parser:** Fix error handling in case of wrong dict `{'A':5,6}` ([#6269](https://github.com/xonsh/xonsh/issues/6269)), @anki-code (@yaxollum, @Techcable)
* **Parser:** Fix loop on `\ ` sequence ([#6194](https://github.com/xonsh/xonsh/issues/6194)), @anki-code (@MajoranaOedipus, @sharktide)
* **Parser:** Fix parsing macro block with comments ([#6216](https://github.com/xonsh/xonsh/issues/6216)), @anki-code (@yaxollum, @alextremblay)
* **Parser:** Fix parsing path with num in case `cd /tmp/123 && ...` ([#6193](https://github.com/xonsh/xonsh/issues/6193)), @anki-code (@JamesParrott, @PodioSpaz)
* **Parser:** Fix single word gulping after block with indent ([#6217](https://github.com/xonsh/xonsh/issues/6217)), @anki-code
* **Parser:** Fix try_subproc_toks issue with wrong wrapping a command with parentheses ([#6233](https://github.com/xonsh/xonsh/issues/6233)), @anki-code (@jun0, @gnewson, @cyb3rmonk)
* **Parser:** Fix ValueError in typed inline env variables e.g. `$QWE=False xonsh --no-rc` ([#6221](https://github.com/xonsh/xonsh/issues/6221)), @anki-code (@jnoortheen)
* **Parser:** Fix regress with parsing `a#b;c` ([#6168](https://github.com/xonsh/xonsh/issues/6168)), @anki-code (@azazel75, @jnoortheen, @Cadair)
* **Parser:** Fix DeprecationWarning on Python 3.14 ([#6279](https://github.com/xonsh/xonsh/issues/6279)), @anki-code (@jaraco, @JamesParrott, @simonLeary42)
* **Parser:** PEP 570 positional-only args support ([#6268](https://github.com/xonsh/xonsh/issues/6268)), @anki-code (@lambda-abstraction)
* **Callable Alias:** Treat unthreadable callable alias exiting ([#6252](https://github.com/xonsh/xonsh/issues/6252)), @anki-code
* **Callable Alias:** Added exception with workaround in case of using explicit unthreadable callable alias in pipe ([#6165](https://github.com/xonsh/xonsh/issues/6165)), @anki-code (@Qyriad, @gforsyth, @jnoortheen)
* **Completer:** Add `@aliases.completer` decorator and fix FuncAlias support ([#6238](https://github.com/xonsh/xonsh/issues/6238)), @anki-code
* **Completer:** Fix CommandPipeline completion: no hanging on blocking properties ([#6229](https://github.com/xonsh/xonsh/issues/6229)), @anki-code (@vadym-shavalda)
* **Completer:** Fix `xpip` completion. Add public API for python modules completion. Add API to register file matching ([#6239](https://github.com/xonsh/xonsh/issues/6239)), @anki-code (@nahoj)
* **Prompt-toolkit:** Fix async prompt race condition when `$ENABLE_ASYNC_PROMPT=True` ([#6250](https://github.com/xonsh/xonsh/issues/6250)), @anki-code
* **Prompt-toolkit:** Restore terminal state after using captured subprocess in key bindings ([#6182](https://github.com/xonsh/xonsh/issues/6182)), @anki-code (@wotsushi, @bobhy, @deeuu, @laloch, @melund, @scopatz, @pigasus55)
* **Prompt-toolkit:** Support retry on EINTR (errno 4) in ptk. Fix exceptions when xonsh runs as a child process ([#6192](https://github.com/xonsh/xonsh/issues/6192)), @anki-code (@vrzh, @dysfungi)
* **Readline:** Fix the case when output disappears in case of no newline character ([#6177](https://github.com/xonsh/xonsh/issues/6177)), @anki-code (@ladyrick, @JamesParrott, @yaxollum)
* **Readline:** Fix the case when completion can remove prefix ([#6230](https://github.com/xonsh/xonsh/issues/6230)), @anki-code (@Nesar21)
* **History:** Switch JSON history backend to atomic file replacing and remove race condition on flushing history at exit ([#6249](https://github.com/xonsh/xonsh/issues/6249)), @anki-code (@hplar, @InfiniteCoder01, @jaraco)
* **History:** Reimplement sqlite history backend `erasedups` and add json history backend support #6293 @anki-code (@FlyingWombat)
* **Glob:** `$DOTGLOB` now controls all forms of globbing uniformly (normal, regex) with a dedicated documentation page ([#6234](https://github.com/xonsh/xonsh/issues/6234)), @anki-code (@inventhouse, @AstraLuma, @gforsyth, @scopatz)
* **Glob:** Remove legacy glob logic that produced issue ([#6231](https://github.com/xonsh/xonsh/issues/6231)), @anki-code (@t184256, @agoose77)
* **Env:** Fix empty path in `$PATH` ([#6169](https://github.com/xonsh/xonsh/issues/6169)), @anki-code
* **Env:** Fix EnvPath (e.g. `$PATH`) mirroring to `os.environ` in case of update and `$UPDATE_OS_ENVIRON=True` ([#6171](https://github.com/xonsh/xonsh/issues/6171)), @anki-code (@NorthIsUp, @AstraLuma, @jaraco, @scopatz)
* **Env:** Detype and detype_all now in sync ([#6195](https://github.com/xonsh/xonsh/issues/6195)), @anki-code (@dconeybe)
* **Env:** Fix `TERM environment variable not set` in `xonsh --no-env` ([#6220](https://github.com/xonsh/xonsh/issues/6220)), @anki-code
* **Env:** Fix RESET in `$XONSH_STDERR_POSTFIX` to colorize stderr properly ([#6218](https://github.com/xonsh/xonsh/issues/6218)), @anki-code (@alvarv, @slacksystem)
* **Env:** Fix `$XONSH_STDERR_PREFIX` ([b7d3298](https://github.com/xonsh/xonsh/commit/b7d32981d25e9e5d270f53a3dcf814bd912658b2)), @anki-code
* **Exec:** Fix `exec` alias to prevent issues with recursive calls and ENOEXEC processing ([#6198](https://github.com/xonsh/xonsh/issues/6198)), @anki-code (@sae13, @g33kex, @lexbailey, @tacaswell, @FlyingWombat, @MajoranaOedipus)
* **Import:** Fix CPython sys_path_init requirement to have current directory in sys.path for executed script ([#6219](https://github.com/xonsh/xonsh/issues/6219)), @anki-code
* **Builtins:** `xcontext` is working on Windows without exception ([#6199](https://github.com/xonsh/xonsh/issues/6199)), @anki-code
* **Style:** Fix #5163 (register_custom_style KeyError) ([ae0c54e](https://github.com/xonsh/xonsh/commit/ae0c54ee5c93fd41b2eb7a90043800c2f1a686eb)), @anki-code (@andrew222651, @dysfungi, @thallium)
* **Mac:** Fix `xonsh.platforms.sysctlbyname` returns bytes instead of string when `return_str=True` ([#6190](https://github.com/xonsh/xonsh/issues/6190)), @Manhhoangvp95
* **Performance:** Reduce expensive operations around getting VCS branch on every prompt ([#6184](https://github.com/xonsh/xonsh/issues/6184)), @anki-code
* **Performance:** Reduce startup time for non-interactive running by ptk shape lazy loading ([#6185](https://github.com/xonsh/xonsh/issues/6185)), @anki-code
* **Stability:** Fix code issues: #6191, #6215, #6254, #6257, #6251, #6276, #6281, #6282, @anki-code (@jaraco, @SirNickolas, @Juncheng-wq)
* **Stability:** Fix _xhj_get_data_dir_files: skip unreadable file instead of exit ([bfacf94](https://github.com/xonsh/xonsh/commit/bfacf9477a4eff996d3898bb1da42ddf8725c44a)), @anki-code
* **Stability:** Fix is_file check ([38162f4](https://github.com/xonsh/xonsh/commit/38162f4095beade88a2d1b1d86b2185d5c64e0af)), @anki-code
* **Stability**: Handle broken pygments plugins in cache discovery #6295 @anki-code (@Marin-Kitagawa)
* **Stability**: Use getuid to detect root instead of user #6296, @anki-code (@jaymehta-g)
* **Windows:** Fix executing scripts and binary files ([#6180](https://github.com/xonsh/xonsh/issues/6180)), @anki-code (@gforsyth, @kalyan860, @jaraco, @dawidsowa, @samueldg, @tahir-hassan)
* **Windows:** Fix raw paths completion ([#6179](https://github.com/xonsh/xonsh/issues/6179)), @anki-code (@zstg, @mwiebe, @adqm, @jaraco, @scopatz, @Ethkuil)
* **Windows:** Fix unstable tests ([#6163](https://github.com/xonsh/xonsh/issues/6163)), @anki-code
* **Windows:** Fix CDLL exception in MSYS2 when running xonsh ([#6176](https://github.com/xonsh/xonsh/issues/6176)), @anki-code
* **Docs:** Fix envvars page and update the main page ([#6214](https://github.com/xonsh/xonsh/issues/6214)), @anki-code
* **Install:** Update mamba git+extras install docs and script ([#6151](https://github.com/xonsh/xonsh/issues/6151)), @ReinerBRO (@jdjohnston, @MrIridescent, @anki-code)
* **Tests:** Add strict check of using `python -m pytest` instead of `pytest` ([#6173](https://github.com/xonsh/xonsh/issues/6173)), @anki-code (@rautyrauty)
* **Tests:** Fix unwanted output and exceptions from tests ([#6178](https://github.com/xonsh/xonsh/issues/6178)), @anki-code
* **Tests:** Split integration tests into fast integration tests and slow stress tests ([#6224](https://github.com/xonsh/xonsh/issues/6224)), @anki-code

## Documentation

* Website: Added dark mode on landing ([#6261](https://github.com/xonsh/xonsh/issues/6261)), @anki-code
* Docs: Complete update: new pages, the sections structure, xonshcon blocks parser, @anki-code