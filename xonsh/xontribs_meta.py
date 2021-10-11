"""
This modules is the place where one would define the xontribs.
"""

import ast
import functools
import importlib.util
from pathlib import Path
import typing as tp

from xonsh.lazyasd import LazyObject, lazyobject


class _XontribPkg(tp.NamedTuple):
    """Class to define package information of a xontrib.

    Attributes
    ----------
    install
        a mapping of tools with respective install commands. e.g. {"pip": "pip install xontrib"}
    license
        license type of the xontrib package
    name
        full name of the package. e.g. "xontrib-argcomplete"
    url
        URL to the homepage of the xontrib package.
    """

    install: tp.Dict[str, str]
    license: str = ""
    name: str = ""
    url: tp.Optional[str] = None


class Xontrib(tp.NamedTuple):
    """Meta class that is used to describe xontribs.

    Attributes
    ----------
    url
        url to the home page of the xontrib.
    description
        short description about the xontrib.
    package
        pkg information for installing the xontrib
    tags
        category.
    """

    url: str = ""
    description: tp.Union[str, LazyObject] = ""
    package: tp.Optional[_XontribPkg] = None
    tags: tp.Tuple[str, ...] = ()


def get_module_docstring(module: str) -> str:
    """Find the module and return its docstring without actual import"""

    spec = importlib.util.find_spec(module)
    if spec and spec.has_location and spec.origin:
        return ast.get_docstring(ast.parse(Path(spec.origin).read_text())) or ""
    return ""


@functools.lru_cache()
def get_xontribs() -> tp.Dict[str, Xontrib]:
    """Return xontrib definitions lazily."""
    return define_xontribs()


def define_xontribs():
    """Xontrib registry."""
    core_pkg = _XontribPkg(
        name="xonsh",
        license="BSD 3-clause",
        install={
            "conda": "conda install -c conda-forge xonsh",
            "pip": "xpip install xonsh",
            "aura": "sudo aura -A xonsh",
            "yaourt": "yaourt -Sa xonsh",
        },
        url="http://xon.sh",
    )
    return {
        "abbrevs": Xontrib(
            url="http://xon.sh",
            description=lazyobject(lambda: get_module_docstring("xontrib.abbrevs")),
            package=core_pkg,
        ),
        "apt_tabcomplete": Xontrib(
            url="https://github.com/DangerOnTheRanger/xonsh-apt-tabcomplete",
            description="Adds tabcomplete functionality to "
            "apt-get/apt-cache inside of xonsh.",
            package=_XontribPkg(
                name="xonsh-apt-tabcomplete",
                license="BSD 2-clause",
                install={"pip": "xpip install xonsh-apt-tabcomplete"},
                url="https://github.com/DangerOnTheRanger/xonsh-apt-tabcomplete",
            ),
        ),
        "argcomplete": Xontrib(
            url="https://github.com/anki-code/xontrib-argcomplete",
            description="Argcomplete support to tab completion of "
            "python and xonsh scripts in xonsh.",
            package=_XontribPkg(
                name="xontrib-argcomplete",
                license="BSD",
                install={"pip": "xpip install xontrib-argcomplete"},
                url="https://github.com/anki-code/xontrib-argcomplete",
            ),
        ),
        "autojump": Xontrib(
            url="https://github.com/wshanks/xontrib-autojump",
            description="autojump support for xonsh",
        ),
        "autovox": Xontrib(
            url="http://xon.sh",
            description="Manages automatic activation of virtual " "environments.",
            package=core_pkg,
        ),
        "autoxsh": Xontrib(
            url="https://github.com/Granitas/xonsh-autoxsh",
            description="Adds automatic execution of xonsh script files "
            "called ``.autoxsh`` when enterting a directory "
            "with ``cd`` function",
            package=_XontribPkg(
                name="xonsh-autoxsh",
                license="GPLv3",
                install={"pip": "xpip install xonsh-autoxsh"},
                url="https://github.com/Granitas/xonsh-autoxsh",
            ),
        ),
        "avox": Xontrib(
            url="https://github.com/AstraLuma/xontrib-avox",
            description="Policy for autovox based on project directories",
            package=_XontribPkg(
                name="xontrib-avox",
                license="GPLv3",
                install={"pip": "xpip install xontrib-avox"},
                url="https://github.com/AstraLuma/xontrib-avox",
            ),
        ),
        "avox_poetry": Xontrib(
            url="https://github.com/jnoortheen/xontrib-avox-poetry",
            description="auto-activate venv as one cd into a poetry project folder. "
            "Activate ``.venv`` inside the project folder is also supported.",
            package=_XontribPkg(
                name="xontrib-avox-poetry",
                license="MIT",
                install={"pip": "xpip install xontrib-avox-poetry"},
                url="https://github.com/jnoortheen/xontrib-avox-poetry",
            ),
        ),
        "back2dir": Xontrib(
            url="https://github.com/anki-code/xontrib-back2dir",
            description="Return to the most recently used directory when "
            "starting the xonsh shell. For example, if you "
            "were in the '/work' directory when you last "
            "exited xonsh, then your next xonsh session will "
            "start in the '/work' directory, instead of your "
            "home directory.",
            package=_XontribPkg(
                name="xontrib-back2dir",
                license="BSD",
                install={"pip": "xpip install xontrib-back2dir"},
                url="https://github.com/anki-code/xontrib-back2dir",
            ),
        ),
        "base16_shell": Xontrib(
            url="https://github.com/ErickTucto/xontrib-base16-shell",
            description="Change base16 shell themes",
        ),
        "bashisms": Xontrib(
            url="http://xon.sh",
            description="Enables additional Bash-like syntax while at the "
            "command prompt. For example, the ``!!`` syntax "
            "for running the previous command is now usable. "
            "Note that these features are implemented as "
            "precommand events and these additions do not "
            "affect the xonsh language when run as script. "
            "That said, you might find them useful if you "
            "have strong muscle memory.\n"
            "\n"
            "**Warning:** This xontrib may modify user "
            "command line input to implement its behavior. To "
            "see the modifications as they are applied (in "
            "unified diffformat), please set ``$XONSH_DEBUG`` "
            "to ``2`` or higher.\n"
            "\n"
            "The xontrib also adds commands: ``alias``, "
            "``export``, ``unset``, ``set``, ``shopt``, "
            "``complete``.",
            package=core_pkg,
        ),
        "broot": Xontrib(
            url="https://github.com/jnoortheen/xontrib-broot",
            description="supports broot with br alias",
            package=_XontribPkg(
                name="xontrib-broot",
                license="MIT",
                install={"pip": "xpip install xontrib-broot"},
                url="https://github.com/jnoortheen/xontrib-broot",
            ),
        ),
        "powerline3": Xontrib(
            url="https://github.com/jnoortheen/xontrib-powerline3",
            description="Powerline theme with native $PROMPT_FIELDS support.",
            package=_XontribPkg(
                name="xontrib-powerline3",
                license="MIT",
                install={"pip": "xpip install xontrib-powerline3"},
                url="https://github.com/jnoortheen/xontrib-powerline3",
            ),
        ),
        "cd": Xontrib(
            url="https://github.com/eugenesvk/xontrib-cd",
            description="'cd' to any path without escaping in xonsh shell "
            "('cd '→'cd! ')",
            package=_XontribPkg(
                name="xontrib-cd",
                license="MIT",
                install={"pip": "xpip install xontrib-cd"},
                url="https://github.com/eugenesvk/xontrib-cd",
            ),
        ),
        "cmd_done": Xontrib(
            url="https://github.com/jnoortheen/xontrib-cmd-durations",
            description="send notification once long-running command is "
            "finished. Adds `long_cmd_duration` field to "
            "$PROMPT_FIELDS. Note: It needs `xdotool` "
            "installed to detect current window.",
            package=_XontribPkg(
                name="xontrib-cmd-durations",
                license="MIT",
                install={"pip": "xpip install xontrib-cmd-durations"},
                url="https://github.com/jnoortheen/xontrib-cmd-durations",
            ),
        ),
        "commands": Xontrib(
            url="https://github.com/jnoortheen/xontrib-commands",
            description="Some useful commands/aliases to use with Xonsh shell",
            package=_XontribPkg(
                name="xontrib-commands",
                license="MIT",
                install={"pip": "xpip install xontrib-commands"},
                url="https://github.com/jnoortheen/xontrib-commands",
            ),
        ),
        "coreutils": Xontrib(
            url="http://xon.sh",
            description="Additional core utilities that are implemented "
            "in xonsh. The current list includes:\n"
            "\n"
            "* cat\n"
            "* echo\n"
            "* pwd\n"
            "* tee\n"
            "* tty\n"
            "* yes\n"
            "\n"
            "In many cases, these may have a lower "
            "performance overhead than the posix command "
            "line utility with the same name. This is "
            "because these tools avoid the need for a full "
            "subprocess call. Additionally, these tools are "
            "cross-platform.",
            package=core_pkg,
        ),
        "direnv": Xontrib(
            url="https://github.com/74th/xonsh-direnv",
            description="Supports direnv.",
            package=_XontribPkg(
                name="xonsh-direnv",
                license="MIT",
                install={"pip": "xpip install xonsh-direnv"},
                url="https://github.com/74th/xonsh-direnv",
            ),
        ),
        "distributed": Xontrib(
            url="http://xon.sh",
            description="The distributed parallel computing library "
            "hooks for xonsh. Importantly this provides a "
            "substitute 'dworker' command which enables "
            "distributed workers to have access to xonsh "
            "builtins.\n"
            "\n"
            "Furthermore, this xontrib adds a 'DSubmitter' "
            "context manager for executing a block "
            "remotely. Moreover, this also adds a "
            "convenience function 'dsubmit()' for creating "
            "DSubmitter and Executor instances at the same "
            "time. Thus users may submit distributed jobs "
            "with::\n"
            "\n"
            "    with dsubmit('127.0.0.1:8786', rtn='x') "
            "as dsub:\n"
            "        x = $(echo I am elsewhere)\n"
            "\n"
            "    res = dsub.future.result()\n"
            "    print(res)\n"
            "\n"
            "This is useful for long running or "
            "non-blocking jobs.",
            package=core_pkg,
        ),
        "docker_tabcomplete": Xontrib(
            url="https://github.com/xsteadfastx/xonsh-docker-tabcomplete",
            description="Adds tabcomplete functionality to " "docker inside of xonsh.",
            package=_XontribPkg(
                name="xonsh-docker-tabcomplete",
                license="MIT",
                install={"pip": "xpip install xonsh-docker-tabcomplete"},
                url="https://github.com/xsteadfastx/xonsh-docker-tabcomplete",
            ),
        ),
        "free_cwd": Xontrib(
            url="http://xon.sh",
            description="Windows only xontrib, to release the lock on the "
            "current directory whenever the prompt is shown. "
            "Enabling this will allow the other programs or "
            "Windows Explorer to delete or rename the current "
            "or parent directories. Internally, it is "
            "accomplished by temporarily resetting CWD to the "
            "root drive folder while waiting at the prompt. "
            "This only works with the prompt_toolkit backend "
            "and can cause cause issues if any extensions are "
            "enabled that hook the prompt and relies on "
            "``os.getcwd()``",
            package=core_pkg,
        ),
        "fzf-widgets": Xontrib(
            url="https://github.com/laloch/xontrib-fzf-widgets",
            description="Adds some fzf widgets to your xonsh shell.",
            package=_XontribPkg(
                name="xontrib-fzf-widgets",
                license="GPLv3",
                install={"pip": "xpip install xontrib-fzf-widgets"},
                url="https://github.com/laloch/xontrib-fzf-widgets",
            ),
        ),
        "gitinfo": Xontrib(
            url="https://github.com/dyuri/xontrib-gitinfo",
            description="Displays git information on entering a repository "
            "folder. Uses ``onefetch`` if available.",
            package=_XontribPkg(
                name="xontrib-gitinfo",
                license="MIT",
                install={"pip": "xpip install xontrib-gitinfo"},
                url="https://github.com/dyuri/xontrib-gitinfo",
            ),
        ),
        "history_encrypt": Xontrib(
            url="https://github.com/anki-code/xontrib-history-encrypt",
            description="History backend that encrypt the xonsh shell commands history "
            "to prevent leaking sensitive data.",
            package=_XontribPkg(
                name="xontrib-history-encrypt",
                license="MIT",
                install={"pip": "xpip install xontrib-history-encrypt"},
                url="https://github.com/anki-code/xontrib-history-encrypt",
            ),
        ),
        "hist_navigator": Xontrib(
            url="https://github.com/jnoortheen/xontrib-hist-navigator",
            description="Move through directory history with nextd "
            "and prevd also with keybindings.",
            package=_XontribPkg(
                name="xontrib-hist-navigator",
                license="MIT",
                install={"pip": "xpip install xontrib-hist-navigator"},
                url="https://github.com/jnoortheen/xontrib-hist-navigator",
            ),
        ),
        "histcpy": Xontrib(
            url="https://github.com/con-f-use/xontrib-histcpy",
            description="Useful aliases and shortcuts for extracting links "
            "and textfrom command output history and putting "
            "them into the clipboard.",
            package=_XontribPkg(
                name="xontrib-histcpy",
                license="GPLv3",
                install={"pip": "xpip install xontrib-histcpy"},
                url="https://github.com/con-f-use/xontrib-histcpy",
            ),
        ),
        "homebrew": Xontrib(
            url="https://github.com/eugenesvk/xontrib-homebrew",
            description="Add Homebrew's shell environment to xonsh shell on macOS/Linux",
            package=_XontribPkg(
                name="xontrib-homebrew",
                license="MIT",
                install={"pip": "xpip install xontrib-homebrew"},
                url="https://github.com/eugenesvk/xontrib-homebrew",
            ),
        ),
        "jedi": Xontrib(
            url="http://xon.sh",
            description="Use Jedi as xonsh's python completer.",
            package=core_pkg,
        ),
        "kitty": Xontrib(
            url="https://github.com/scopatz/xontrib-kitty",
            description="Xonsh hooks for the Kitty terminal emulator.",
            package=_XontribPkg(
                name="xontrib-kitty",
                license="BSD-3-Clause",
                install={
                    "conda": "conda install -c conda-forge " "xontrib-kitty",
                    "pip": "xpip install xontrib-kitty",
                },
                url="https://github.com/scopatz/xontrib-kitty",
            ),
        ),
        "macro_lib": Xontrib(
            url="https://github.com/anki-code/xontrib-macro-lib",
            description="Library of the useful macros for the xonsh shell.",
            package=_XontribPkg(
                name="xontrib-macro-lib",
                license="BSD",
                install={"pip": "xpip install xontrib-macro-lib"},
                url="https://github.com/anki-code/xontrib-macro-lib",
            ),
        ),
        "mpl": Xontrib(
            url="http://xon.sh",
            description="Matplotlib hooks for xonsh, including the new 'mpl' "
            "alias that displays the current figure on the screen.",
            package=core_pkg,
        ),
        "onepath": Xontrib(
            url="https://github.com/anki-code/xontrib-onepath",
            description="When you click to a file or folder in graphical "
            "OS they will be opened in associated app.The "
            "xontrib-onepath brings the same logic for the "
            "xonsh shell. Type the filename or pathwithout "
            "preceding command and an associated action will "
            "be executed. The actions are customizable.",
            package=_XontribPkg(
                name="xontrib-onepath",
                license="BSD",
                install={"pip": "xpip install xontrib-onepath"},
                url="https://github.com/anki-code/xontrib-onepath",
            ),
        ),
        "output_search": Xontrib(
            url="https://github.com/anki-code/xontrib-output-search",
            description="Get identifiers, names, paths, URLs and "
            "words from the previous command output and "
            "use them for the next command.",
            package=_XontribPkg(
                name="xontrib-output-search",
                license="BSD",
                install={"pip": "xpip install xontrib-output-search"},
                url="https://github.com/tokenizer/xontrib-output-search",
            ),
        ),
        "pdb": Xontrib(
            url="http://xon.sh",
            description="Simple built-in debugger. Runs pdb on reception of "
            "SIGUSR1 signal.",
            package=core_pkg,
        ),
        "pipeliner": Xontrib(
            url="https://github.com/anki-code/xontrib-pipeliner",
            description="Let your pipe lines flow thru the Python code " "in xonsh.",
            package=_XontribPkg(
                name="xontrib-pipeliner",
                license="MIT",
                install={"pip": "xpip install xontrib-pipeliner"},
                url="https://github.com/anki-code/xontrib-pipeliner",
            ),
        ),
        "powerline": Xontrib(
            url="https://github.com/santagada/xontrib-powerline",
            description="Powerline for Xonsh shell",
            package=_XontribPkg(
                name="xontrib-powerline",
                license="MIT",
                install={"pip": "xpip install xontrib-powerline"},
                url="https://github.com/santagada/xontrib-powerline",
            ),
        ),
        "powerline2": Xontrib(
            url="https://github.com/vaaaaanquish/xontrib-powerline2",
            description="Powerline for Xonsh shell forked from "
            "santagada/xontrib-powerline",
            package=_XontribPkg(
                name="xontrib-powerline2",
                license="MIT",
                install={"pip": "xpip install xontrib-powerline2"},
                url="https://github.com/vaaaaanquish/xontrib-powerline2",
            ),
        ),
        "powerline_binding": Xontrib(
            url="https://github.com/dyuri/xontrib-powerline-binding",
            description="Uses powerline to render the xonsh " "prompt",
            package=_XontribPkg(
                name="xontrib-powerline-binding",
                license="MIT",
                install={"pip": "xpip install xontrib-powerline-binding"},
                url="https://github.com/dyuri/xontrib-powerline-binding",
            ),
        ),
        "prompt_bar": Xontrib(
            url="https://github.com/anki-code/xontrib-prompt-bar",
            description="An elegance bar style for prompt.",
            package=_XontribPkg(
                name="xontrib-prompt-bar",
                license="MIT",
                install={"pip": "xpip install xontrib-prompt-bar"},
                url="https://github.com/anki-code/xontrib-prompt-bar",
            ),
        ),
        "prompt_ret_code": Xontrib(
            url="http://xon.sh",
            description="Adds return code info to the prompt",
            package=core_pkg,
        ),
        "prompt_starship": Xontrib(
            url="https://github.com/anki-code/xontrib-prompt-starship",
            description="Starship prompt in xonsh shell.",
            package=_XontribPkg(
                name="xontrib-prompt-starship",
                license="MIT",
                install={"pip": "xpip install xontrib-prompt-starship"},
                url="https://github.com/anki-code/xontrib-prompt-starship",
            ),
        ),
        "prompt_vi_mode": Xontrib(
            url="https://github.com/t184256/xontrib-prompt-vi-mode",
            description="vi-mode status formatter for xonsh prompt",
            package=_XontribPkg(
                name="xontrib-prompt-vi-mode",
                license="MIT",
                install={"pip": "xpip install xontrib-prompt-vi-mode"},
                url="https://github.com/t184256/xontrib-prompt-vi-mode",
            ),
        ),
        "pyenv": Xontrib(
            url="https://github.com/dyuri/xontrib-pyenv",
            description="pyenv integration for xonsh.",
            package=_XontribPkg(
                name="xontrib-pyenv",
                license="MIT",
                install={"pip": "xpip install xontrib-pyenv"},
                url="https://github.com/dyuri/xontrib-pyenv",
            ),
        ),
        "pyrtn": Xontrib(
            url="https://github.com/dyuri/xontrib-pyrtn",
            description="IPython like In[]/Out[] to access python return values in the current session.",
            package=_XontribPkg(
                name="xontrib-pyrtn",
                license="MIT",
                install={"pip": "xpip install xontrib-pyrtn"},
                url="https://github.com/dyuri/xontrib-pyrtn",
            ),
        ),
        "readable-traceback": Xontrib(
            url="https://github.com/6syun9/xontrib-readable-traceback",
            description="Make traceback easier to see for " "xonsh.",
            package=_XontribPkg(
                name="xontrib-readable-traceback",
                license="MIT",
                install={"pip": "xpip install xontrib-readable-traceback"},
                url="https://github.com/6syun9/xontrib-readable-traceback",
            ),
        ),
        "schedule": Xontrib(
            url="https://github.com/AstraLuma/xontrib-schedule",
            description="Xonsh Task Scheduling",
            package=_XontribPkg(
                name="xontrib-schedule",
                license="MIT",
                install={"pip": "xpip install xontrib-schedule"},
                url="https://github.com/AstraLuma/xontrib-schedule",
            ),
        ),
        "scrapy_tabcomplete": Xontrib(
            url="https://github.com/Granitas/xonsh-scrapy-tabcomplete",
            description="Adds tabcomplete functionality to " "scrapy inside of xonsh.",
            package=_XontribPkg(
                name="xonsh-scrapy-tabcomplete",
                license="GPLv3",
                install={"pip": "xpip install xonsh-scrapy-tabcomplete"},
                url="https://github.com/Granitas/xonsh-scrapy-tabcomplete",
            ),
        ),
        "sh": Xontrib(
            url="https://github.com/anki-code/xontrib-sh",
            description="Paste and run commands from bash, zsh, fish in xonsh "
            "shell.",
            package=_XontribPkg(
                name="xontrib-sh",
                license="MIT",
                install={"pip": "xpip install xontrib-sh"},
                url="https://github.com/anki-code/xontrib-sh",
            ),
        ),
        "ssh_agent": Xontrib(
            url="https://github.com/dyuri/xontrib-ssh-agent",
            description="ssh-agent integration",
            package=_XontribPkg(
                name="xontrib-ssh-agent",
                license="MIT",
                install={"pip": "xpip install xontrib-ssh-agent"},
                url="https://github.com/dyuri/xontrib-ssh-agent",
            ),
        ),
        "tcg": Xontrib(
            url="https://github.com/zasdfgbnm/tcg/tree/master/shells/xonsh",
            description="tcg integration.",
            package=_XontribPkg(
                name="xonsh-tcg",
                license="MIT",
                install={"pip": "xpip install xonsh-tcg"},
                url="https://github.com/zasdfgbnm/tcg/tree/master/shells/xonsh",
            ),
        ),
        "vox": Xontrib(
            url="http://xon.sh",
            description="Python virtual environment manager for xonsh.",
            package=core_pkg,
        ),
        "vox_tabcomplete": Xontrib(
            url="https://github.com/Granitosaurus/xonsh-vox-tabcomplete",
            description="Adds tabcomplete functionality to vox " "inside of xonsh.",
            package=_XontribPkg(
                name="xonsh-vox-tabcomplete",
                license="GPLv3",
                install={"pip": "xpip install xonsh-vox-tabcomplete"},
                url="https://github.com/Granitosaurus/xonsh-vox-tabcomplete",
            ),
        ),
        "whole_word_jumping": Xontrib(
            url="http://xon.sh",
            description="Jumping across whole words "
            "(non-whitespace) with Ctrl+Left/Right. "
            "Alt+Left/Right remains unmodified to "
            "jump over smaller word segments. "
            "Shift+Delete removes the whole word.",
            package=core_pkg,
        ),
        "xo": Xontrib(
            url="https://github.com/scopatz/xo",
            description="Adds an 'xo' alias to run the exofrills text editor in "
            "the current Python interpreter session. This shaves "
            "off a bit of the startup time when running your "
            "favorite, minimal text editor.",
            package=_XontribPkg(
                name="exofrills",
                license="WTFPL",
                install={
                    "conda": "conda install -c conda-forge xo",
                    "pip": "xpip install exofrills",
                },
                url="http://exofrills.org",
            ),
        ),
        "xog": Xontrib(
            url="http://xon.sh",
            description="Adds a simple command to establish and print "
            "temporary traceback log file.",
            package=core_pkg,
        ),
        "xpg": Xontrib(
            url="https://github.com/fengttt/xsh/tree/master/py",
            description="Run/plot/explain sql query for PostgreSQL.",
            package=_XontribPkg(
                name="xontrib-xpg",
                license="Apache",
                install={"pip": "xpip install xontrib-xpg"},
                url="https://github.com/fengttt/xsh/py",
            ),
        ),
        "z": Xontrib(
            url="https://github.com/AstraLuma/xontrib-z",
            description="Tracks your most used directories, based on 'frecency'.",
            package=_XontribPkg(
                name="xontrib-z",
                license="GPLv3",
                install={"pip": "xpip install xontrib-z"},
                url="https://github.com/AstraLuma/xontrib-z",
            ),
        ),
        "zoxide": Xontrib(
            url="https://github.com/dyuri/xontrib-zoxide",
            description="Zoxide integration for xonsh.",
            package=_XontribPkg(
                name="xontrib-zoxide",
                license="MIT",
                install={"pip": "xpip install xontrib-zoxide"},
                url="https://github.com/dyuri/xontrib-zoxide",
            ),
        ),
    }
