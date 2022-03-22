"""
API for Vox, the Python virtual environment manager for xonsh.

Vox defines several events related to the life cycle of virtual environments:

* ``vox_on_create(env: str) -> None``
* ``vox_on_activate(env: str, path: pathlib.Path) -> None``
* ``vox_on_deactivate(env: str, path: pathlib.Path) -> None``
* ``vox_on_delete(env: str) -> None``
"""
import collections.abc
import logging
import os
import shutil
import subprocess as sp
import sys
import typing

from xonsh.built_ins import XSH

# This is because builtins aren't globally created during testing.
# FIXME: Is there a better way?
from xonsh.events import events
from xonsh.platform import ON_POSIX, ON_WINDOWS

events.doc(
    "vox_on_create",
    """
vox_on_create(env: str) -> None

Fired after an environment is created.
""",
)

events.doc(
    "vox_on_activate",
    """
vox_on_activate(env: str, path: pathlib.Path) -> None

Fired after an environment is activated.
""",
)

events.doc(
    "vox_on_deactivate",
    """
vox_on_deactivate(env: str, path: pathlib.Path) -> None

Fired after an environment is deactivated.
""",
)

events.doc(
    "vox_on_delete",
    """
vox_on_delete(env: str) -> None

Fired after an environment is deleted (through vox).
""",
)


class VirtualEnvironment(typing.NamedTuple):
    env: str
    bin: str
    lib: str
    inc: str


def _subdir_names():
    """
    Gets the names of the special dirs in a venv.

    This is not necessarily exhaustive of all the directories that could be in a venv, and there
    may additional logic to get to useful places.
    """
    if ON_WINDOWS:
        return "Scripts", "Lib", "Include"
    elif ON_POSIX:
        return "bin", "lib", "include"
    else:
        raise OSError("This OS is not supported.")


def _mkvenv(env_dir):
    """
    Constructs a VirtualEnvironment based on the given base path.

    This only cares about the platform. No filesystem calls are made.
    """
    env_dir = os.path.abspath(env_dir)
    if ON_WINDOWS:
        binname = os.path.join(env_dir, "Scripts")
        incpath = os.path.join(env_dir, "Include")
        libpath = os.path.join(env_dir, "Lib", "site-packages")
    elif ON_POSIX:
        binname = os.path.join(env_dir, "bin")
        incpath = os.path.join(env_dir, "include")
        libpath = os.path.join(
            env_dir, "lib", "python%d.%d" % sys.version_info[:2], "site-packages"
        )
    else:
        raise OSError("This OS is not supported.")

    return VirtualEnvironment(env_dir, binname, libpath, incpath)


class EnvironmentInUse(Exception):
    """The given environment is currently activated, and the operation cannot be performed."""


class NoEnvironmentActive(Exception):
    """No environment is currently activated, and the operation cannot be performed."""


class Vox(collections.abc.Mapping):
    """API access to Vox and virtual environments, in a dict-like format.

    Makes use of the VirtualEnvironment namedtuple:

    1. ``env``: The full path to the environment
    2. ``bin``: The full path to the bin/Scripts directory of the environment
    """

    def __init__(self, force_removals=False):
        if not XSH.env.get("VIRTUALENV_HOME"):
            home_path = os.path.expanduser("~")
            self.venvdir = os.path.join(home_path, ".virtualenvs")
            XSH.env["VIRTUALENV_HOME"] = self.venvdir
        else:
            self.venvdir = XSH.env["VIRTUALENV_HOME"]
        self.force_removals = force_removals
        self.sub_dirs = _subdir_names()

    def create(
        self,
        name,
        interpreter=None,
        system_site_packages=False,
        symlinks=False,
        with_pip=True,
        prompt=None,
    ):
        """Create a virtual environment in $VIRTUALENV_HOME with python3's ``venv``.

        Parameters
        ----------
        name : str
            Virtual environment name
        interpreter: str
            Python interpreter used to create the virtual environment.
            Can be configured via the $VOX_DEFAULT_INTERPRETER environment variable.
        system_site_packages : bool
            If True, the system (global) site-packages dir is available to
            created environments.
        symlinks : bool
            If True, attempt to symlink rather than copy files into virtual
            environment.
        with_pip : bool
            If True, ensure pip is installed in the virtual environment. (Default is True)
        prompt: str
            Provides an alternative prompt prefix for this environment.
        """
        if interpreter is None:
            interpreter = _get_vox_default_interpreter()
            print(f"Using Interpreter: {interpreter}")

        # NOTE: clear=True is the same as delete then create.
        # NOTE: upgrade=True is its own method
        if isinstance(name, os.PathLike):
            env_path = os.fspath(name)
        else:
            env_path = os.path.join(self.venvdir, name)
        if not self._check_reserved(env_path):
            raise ValueError(
                "venv can't contain reserved names ({})".format(
                    ", ".join(self.sub_dirs)
                )
            )

        self._create(
            env_path,
            interpreter,
            system_site_packages,
            symlinks,
            with_pip,
            prompt=prompt,
        )
        events.vox_on_create.fire(name=name)

    def upgrade(self, name, symlinks=False, with_pip=True, interpreter=None):
        """Create a virtual environment in $VIRTUALENV_HOME with python3's ``venv``.

        WARNING: If a virtual environment was created with symlinks or without PIP, you must
        specify these options again on upgrade.

        Parameters
        ----------
        name : str
            Virtual environment name
        interpreter: str
            The Python interpreter used to create the virtualenv
        symlinks : bool
            If True, attempt to symlink rather than copy files into virtual
            environment.
        with_pip : bool
            If True, ensure pip is installed in the virtual environment.
        """

        if interpreter is None:
            interpreter = _get_vox_default_interpreter()
            print(f"Using Interpreter: {interpreter}")

        # venv doesn't reload this, so we have to do it ourselves.
        # Is there a bug for this in Python? There should be.
        venv = self[name]
        cfgfile = os.path.join(venv.env, "pyvenv.cfg")
        cfgops = {}
        with open(cfgfile) as cfgfile:
            for line in cfgfile:
                line = line.strip()
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfgops[k.strip()] = v.strip()
        flags = {
            "system_site_packages": cfgops["include-system-site-packages"] == "true",
            "symlinks": symlinks,
            "with_pip": with_pip,
        }
        prompt = cfgops.get("prompt")
        if prompt:
            flags["prompt"] = prompt.lstrip("'\"").rstrip("'\"")
        # END things we shouldn't be doing.

        # Ok, do what we came here to do.
        self._create(venv.env, interpreter, upgrade=True, **flags)
        return venv

    @staticmethod
    def _create(
        env_path,
        interpreter,
        system_site_packages=False,
        symlinks=False,
        with_pip=True,
        upgrade=False,
        prompt=None,
    ):
        version_output = sp.check_output(
            [interpreter, "--version"], stderr=sp.STDOUT, text=True
        )

        interpreter_major_version = int(version_output.split()[-1].split(".")[0])
        module = "venv" if interpreter_major_version >= 3 else "virtualenv"
        system_site_packages = "--system-site-packages" if system_site_packages else ""
        symlinks = "--symlinks" if symlinks and interpreter_major_version >= 3 else ""
        with_pip = "" if with_pip else "--without-pip"
        upgrade = "--upgrade" if upgrade else ""

        cmd = [
            interpreter,
            "-m",
            module,
            env_path,
            system_site_packages,
            symlinks,
            with_pip,
            upgrade,
        ]
        if prompt and module == "venv":
            cmd.extend(["--prompt", prompt])

        cmd = [arg for arg in cmd if arg]  # remove empty args
        logging.debug(cmd)

        sp.check_call(cmd)

    def _check_reserved(self, name):
        return (
            os.path.basename(name) not in self.sub_dirs
        )  # FIXME: Check the middle components, too

    def __getitem__(self, name) -> "VirtualEnvironment":
        """Get information about a virtual environment.

        Parameters
        ----------
        name : str or Ellipsis
            Virtual environment name or absolute path. If ... is given, return
            the current one (throws a KeyError if there isn't one).
        """
        if name is ...:
            env = XSH.env
            env_paths = [env["VIRTUAL_ENV"]]
        elif isinstance(name, os.PathLike):
            env_paths = [os.fspath(name)]
        else:
            if not self._check_reserved(name):
                # Don't allow a venv that could be a venv special dir
                raise KeyError()

            env_paths = []
            if os.path.isdir(name):
                env_paths += [name]
            env_paths += [os.path.join(self.venvdir, name)]

        for ep in env_paths:
            ve = _mkvenv(ep)

            # Actually check if this is an actual venv or just a organizational directory
            # eg, if 'spam/eggs' is a venv, reject 'spam'
            if not os.path.exists(ve.bin):
                continue
            return ve
        else:
            raise KeyError()

    def __contains__(self, name):
        # For some reason, MutableMapping seems to do this against iter, which is just silly.
        try:
            self[name]
        except KeyError:
            return False
        else:
            return True

    def get_binary_path(self, binary: str, *dirs: str):
        bin_, _, _ = self.sub_dirs
        python_exec = binary
        if ON_WINDOWS and not python_exec.endswith(".exe"):
            python_exec += ".exe"
        return os.path.join(*dirs, bin_, python_exec)

    def __iter__(self):
        """List available virtual environments found in $VIRTUALENV_HOME."""
        for dirpath, dirnames, _ in os.walk(self.venvdir):
            python_exec = self.get_binary_path("python", dirpath)
            if os.access(python_exec, os.X_OK):
                yield dirpath[len(self.venvdir) + 1 :]  # +1 is to remove the separator
                dirnames.clear()

    def __len__(self):
        """Counts known virtual environments, using the same rules as iter()."""
        line = 0
        for _ in self:
            line += 1
        return line

    def active(self):
        """Get the name of the active virtual environment.

        You can use this as a key to get further information.

        Returns None if no environment is active.
        """
        env = XSH.env
        if "VIRTUAL_ENV" not in env:
            return
        env_path = env["VIRTUAL_ENV"]
        if env_path.startswith(self.venvdir):
            name = env_path[len(self.venvdir) :]
            if name[0] in "/\\":
                name = name[1:]
            return name
        else:
            return env_path

    def activate(self, name):
        """
        Activate a virtual environment.

        Parameters
        ----------
        name : str
            Virtual environment name or absolute path.
        """
        env = XSH.env
        ve = self[name]
        if "VIRTUAL_ENV" in env:
            self.deactivate()

        type(self).oldvars = {"PATH": list(env["PATH"])}
        env["PATH"].insert(0, ve.bin)
        env["VIRTUAL_ENV"] = ve.env
        if "PYTHONHOME" in env:
            type(self).oldvars["PYTHONHOME"] = env.pop("PYTHONHOME")

        events.vox_on_activate.fire(name=name, path=ve.env)

    def deactivate(self):
        """
        Deactivate the active virtual environment. Returns its name.
        """
        env = XSH.env
        if "VIRTUAL_ENV" not in env:
            raise NoEnvironmentActive("No environment currently active.")

        env_name = self.active()

        if hasattr(type(self), "oldvars"):
            for k, v in type(self).oldvars.items():
                env[k] = v
            del type(self).oldvars

        del env["VIRTUAL_ENV"]

        events.vox_on_deactivate.fire(name=env_name, path=self[env_name].env)
        return env_name

    def __delitem__(self, name):
        """
        Permanently deletes a virtual environment.

        Parameters
        ----------
        name : str
            Virtual environment name or absolute path.
        """
        env_path = self[name].env
        try:
            if self[...].env == env_path:
                raise EnvironmentInUse(
                    'The "%s" environment is currently active.' % name
                )
        except KeyError:
            # No current venv, ... fails
            pass

        env_path = os.path.abspath(env_path)
        if not self.force_removals:
            print(f"The directory {env_path}")
            print("and all of its content will be deleted.")
            answer = input("Do you want to continue? [Y/n]")
            if "n" in answer:
                return

        shutil.rmtree(env_path)

        events.vox_on_delete.fire(name=name)


def _get_vox_default_interpreter():
    """Return the interpreter set by the $VOX_DEFAULT_INTERPRETER if set else sys.executable"""
    default = "python3"
    if default in XSH.commands_cache:
        default = XSH.commands_cache.locate_binary(default)
    else:
        default = sys.executable
    return XSH.env.get("VOX_DEFAULT_INTERPRETER", default)
