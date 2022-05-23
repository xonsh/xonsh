"""Python virtual environment manager for xonsh."""
import os.path
import subprocess
import tempfile
import typing as tp
from pathlib import Path

import xonsh.cli_utils as xcli
import xontrib.voxapi as voxapi
from xonsh.built_ins import XSH, XonshSession
from xonsh.dirstack import pushd_fn
from xonsh.platform import ON_WINDOWS
from xonsh.tools import XonshError

__all__ = ()


def venv_names_completer(command, alias: "VoxHandler", **_):
    envs = alias.vox.keys()
    from xonsh.completers.path import complete_dir

    yield from envs

    paths, _ = complete_dir(command)
    yield from paths


def py_interpreter_path_completer(xsh, **_):
    for _, (path, is_alias) in xsh.commands_cache.all_commands.items():
        if not is_alias and ("/python" in path or "/pypy" in path):
            yield path


_venv_option = xcli.Annotated[
    tp.Optional[str],
    xcli.Arg(metavar="ENV", nargs="?", completer=venv_names_completer),
]


class VoxHandler(xcli.ArgParserAlias):
    """Vox is a virtual environment manager for xonsh."""

    def build(self):
        """lazily called during dispatch"""
        self.vox = voxapi.Vox()
        parser = self.create_parser(prog="vox")

        parser.add_command(self.new, aliases=["create"])
        parser.add_command(self.activate, aliases=["workon", "enter"])
        parser.add_command(self.deactivate, aliases=["exit"])
        parser.add_command(self.list, aliases=["ls"])
        parser.add_command(self.remove, aliases=["rm", "delete", "del"])
        parser.add_command(self.info)
        parser.add_command(self.runin)
        parser.add_command(self.runin_all)
        parser.add_command(self.toggle_ssp)
        parser.add_command(self.wipe)
        parser.add_command(self.project_set)
        parser.add_command(self.project_get)
        parser.add_command(self.upgrade)

        return parser

    def hook_pre_add_argument(self, param: str, func, flags, kwargs):
        if func.__name__ in {"new", "upgrade"}:
            if ON_WINDOWS and param == "symlinks":
                # copies by default on windows
                kwargs["default"] = False
                kwargs["action"] = "store_true"
                kwargs["help"] = "Try to use symlinks rather than copies"
                flags = ["--symlinks"]
        return flags, kwargs

    def hook_post_add_argument(self, action, param: str, **_):
        if param == "interpreter":
            action.completer = py_interpreter_path_completer

    def new(
        self,
        name: xcli.Annotated[str, xcli.Arg(metavar="ENV")],
        interpreter: "str|None" = None,
        system_site_packages=False,
        symlinks=True,
        without_pip=False,
        activate=False,
        temporary=False,
        packages: xcli.Annotated[tp.Sequence[str], xcli.Arg(nargs="*")] = (),
        requirements: xcli.Annotated[tp.Sequence[str], xcli.Arg(action="append")] = (),
        link_project_dir=False,
        prompt: "str|None" = None,
    ):
        """Create a virtual environment in $VIRTUALENV_HOME with python3's ``venv``.

        Parameters
        ----------
        name : str
            Virtual environment name
        interpreter: -p, --interpreter
            Python interpreter used to create the virtual environment.
            Can be configured via the $VOX_DEFAULT_INTERPRETER environment variable.
        system_site_packages : --system-site-packages, --ssp
            If True, the system (global) site-packages dir is available to
            created environments.
        symlinks : --copies
            Try to use copies rather than symlinks.
        without_pip : --without-pip, --wp
            Skips installing or upgrading pip in the virtual environment
        activate : -a, --activate
            Activate the newly created virtual environment.
        temporary: -t, --temp
            Create the virtualenv under a temporary directory.
        packages: -i, --install
            Install one or more packages (by repeating the option) after the environment is created using pip
        requirements: -r, --requirements
            The argument value is passed to ``pip -r`` to be installed.
        link_project_dir: -l, --link, --link-project
            Associate the current directory with the new environment.
        prompt: --prompt
            Provides an alternative prompt prefix for this environment.
        """

        self.out("Creating environment...")

        if temporary:
            path = tempfile.mkdtemp(prefix=f"vox-env-{name}")
            name = os.path.join(path, name)

        self.vox.create(
            name,
            system_site_packages=system_site_packages,
            symlinks=symlinks,
            with_pip=(not without_pip),
            interpreter=interpreter,
            prompt=prompt,
        )
        if link_project_dir:
            self.project_set(name)

        if packages:
            self.runin(name, ["pip", "install", *packages])

        if requirements:

            def _generate_args():
                for req in requirements:
                    yield "-r"
                    yield req

            self.runin(name, ["pip", "install"] + list(_generate_args()))

        if activate:
            self.activate(name)
            self.out(f"Environment {name!r} created and activated.\n")
        else:
            self.out(
                f'Environment {name!r} created. Activate it with "vox activate {name}".\n'
            )

    def activate(
        self,
        name: _venv_option = None,
        no_cd=False,
    ):
        """Activate a virtual environment.

        Parameters
        ----------
        name
            The environment to activate.
            ENV can be either a name from the venvs shown by ``vox list``
            or the path to an arbitrary venv
        no_cd: -n, --no-cd
            Do not change current working directory even if a project path is associated with ENV.
        """

        if name is None:
            return self.list()

        try:
            self.vox.activate(name)
        except KeyError:
            raise self.Error(
                f'This environment doesn\'t exist. Create it with "vox new {name}"',
            )

        self.out(f'Activated "{name}".\n')
        if not no_cd:
            project_dir = self._get_project_dir(name)
            if project_dir:
                pushd_fn(project_dir)

    def deactivate(self, remove=False, force=False):
        """Deactivate the active virtual environment.

        Parameters
        ----------
        remove: -r, --remove
            Remove the virtual environment after leaving it.
        force: -f, --force-removal
            Remove the virtual environment without prompt
        """

        if self.vox.active() is None:
            raise self.Error(
                'No environment currently active. Activate one with "vox activate".\n',
            )
        env_name = self.vox.deactivate()
        if remove:
            self.vox.force_removals = force
            del self.vox[env_name]
            self.out(f'Environment "{env_name}" deactivated and removed.\n')
        else:
            self.out(f'Environment "{env_name}" deactivated.\n')

    def list(self):
        """List available virtual environments."""

        try:
            envs = sorted(self.vox.keys())
        except PermissionError:
            raise self.Error("No permissions on VIRTUALENV_HOME")

        if not envs:
            raise self.Error(
                'No environments available. Create one with "vox new".\n',
            )

        self.out("Available environments:")
        self.out("\n".join(envs))

    def remove(
        self,
        names: xcli.Annotated[
            tp.List[str],
            xcli.Arg(metavar="ENV", nargs="+", completer=venv_names_completer),
        ],
        force=False,
    ):
        """Remove virtual environments.

        Parameters
        ----------
        names
            The environments to remove. ENV can be either a name from the venvs shown by vox
            list or the path to an arbitrary venv
        force : -f, --force
            Delete virtualenv without prompt
        """
        self.vox.force_removals = force
        for name in names:
            try:
                del self.vox[name]
            except voxapi.EnvironmentInUse:
                raise self.Error(
                    f'The "{name}" environment is currently active. '
                    'In order to remove it, deactivate it first with "vox deactivate".\n',
                )
            except KeyError:
                raise self.Error(f'"{name}" environment doesn\'t exist.\n')
            else:
                self.out(f'Environment "{name}" removed.')
        self.out()

    def _in_venv(self, env_dir: str, command: str, *args, **kwargs):
        env = {**XSH.env.detype(), "VIRTUAL_ENV": env_dir}

        bin_path = os.path.join(env_dir, self.vox.sub_dirs[0])
        env["PATH"] = os.pathsep.join([bin_path, env["PATH"]])

        for key in ("PYTHONHOME", "__PYVENV_LAUNCHER__"):
            env.pop(key, None)

        try:
            return subprocess.check_call(
                [command] + list(args), shell=bool(ON_WINDOWS), env=env, **kwargs
            )
            # need to have shell=True on windows, otherwise the PYTHONPATH
            # won't inherit the PATH
        except OSError as e:
            if e.errno == 2:
                raise self.Error(f"Unable to find {command}")
            raise

    def runin(
        self,
        venv: xcli.Annotated[
            str,
            xcli.Arg(completer=venv_names_completer),
        ],
        args: xcli.Annotated[tp.Sequence[str], xcli.Arg(nargs="...")],
    ):
        """Run the command in the given environment

        Parameters
        ----------
        venv
            The environment to run the command for
        args
            The actual command to run

        Examples
        --------
          vox runin venv1 black --check-only
        """
        env_dir = self._get_env_dir(venv)
        if not args:
            raise self.Error("No command is passed")
        self._in_venv(env_dir, *args)

    def runin_all(
        self,
        args: xcli.Annotated[tp.Sequence[str], xcli.Arg(nargs="...")],
    ):
        """Run the command in all environments found under $VIRTUALENV_HOME

        Parameters
        ----------
        args
            The actual command to run with arguments
        """
        errors = False
        for env in self.vox:
            self.out("\n%s:" % env)
            try:
                self.runin(env, *args)
            except subprocess.CalledProcessError as e:
                errors = True
                self.err(e)
        self.parser.exit(errors)

    def _sitepackages_dir(self, venv_path: str):
        env_python = self.vox.get_binary_path("python", venv_path)
        if not os.path.exists(env_python):
            raise self.Error("no virtualenv active")

        return Path(
            subprocess.check_output(
                [
                    str(env_python),
                    "-c",
                    "import distutils; \
    print(distutils.sysconfig.get_python_lib())",
                ]
            ).decode()
        )

    def _get_env_dir(self, venv=None):
        venv = venv or ...
        try:
            env_dir = self.vox[venv].env
        except KeyError:
            # check whether the venv is a valid path to an environment
            if (
                isinstance(venv, str)
                and os.path.exists(venv)
                and os.path.exists(self.vox.get_binary_path("python", venv))
            ):
                return venv
            raise XonshError("No virtualenv is found")
        return env_dir

    def toggle_ssp(self):
        """Controls whether the active virtualenv will access the packages
        in the global Python site-packages directory."""
        # https://virtualenv.pypa.io/en/legacy/userguide.html#the-system-site-packages-option
        env_dir = self._get_env_dir()  # current
        site = self._sitepackages_dir(env_dir)
        ngsp_file = site.parent / "no-global-site-packages.txt"
        if ngsp_file.exists():
            ngsp_file.unlink()
            self.out("Enabled global site-packages")
        else:
            with ngsp_file.open("w"):
                self.out("Disabled global site-packages")

    def project_set(
        self,
        venv: _venv_option = None,
        project_path=None,
    ):
        """Bind an existing virtualenv to an existing project.

        Parameters
        ----------
        venv
            Name of the virtualenv, while the default being currently active venv.
        project_path
            Path to the project, while the default being current directory.
        """
        env_dir = self._get_env_dir(venv)  # current

        project = os.path.abspath(project_path or ".")
        if not os.path.exists(env_dir):
            raise self.Error(f"Environment '{env_dir}' doesn't exist.")
        if not os.path.isdir(project):
            raise self.Error(f"{project} does not exist")

        project_file = self._get_project_file()
        project_file.write_text(project)

    def _get_project_file(
        self,
        venv=None,
    ):
        env_dir = Path(self._get_env_dir(venv))  # current
        return env_dir / ".project"

    def _get_project_dir(self, venv=None):
        project_file = self._get_project_file(venv)
        if project_file.exists():
            project_dir = project_file.read_text()
            if os.path.exists(project_dir):
                return project_dir

    def project_get(self, venv: _venv_option = None):
        """Return a virtualenv's project directory.

        Parameters
        ----------
        venv
            Name of the virtualenv under $VIRTUALENV_HOME, while default being currently active venv.
        """
        project_dir = self._get_project_dir(venv)
        if project_dir:
            self.out(project_dir)
        else:
            project_file = self._get_project_file(venv)
            raise self.Error(
                f"Corrupted or outdated: {project_file}\nDirectory: {project_dir} doesn't exist."
            )

    def wipe(self, venv: _venv_option = None):
        """Remove all installed packages from the current (or supplied) env.

        Parameters
        ----------
        venv
            name of the venv. Defaults to currently active venv
        """
        env_dir = self._get_env_dir(venv)
        pip_bin = self.vox.get_binary_path("pip", env_dir)
        all_pkgs = set(
            subprocess.check_output([pip_bin, "freeze", "--local"])
            .decode()
            .splitlines()
        )
        pkgs = {p for p in all_pkgs if len(p.split("==")) == 2}
        ignored = sorted(all_pkgs - pkgs)
        to_remove = {p.split("==")[0] for p in pkgs}
        if to_remove:
            self.out("Ignoring:\n %s" % "\n ".join(ignored))
            self.out("Uninstalling packages:\n %s" % "\n ".join(to_remove))
            return subprocess.run([pip_bin, "uninstall", "-y", *to_remove])
        else:
            self.out("Nothing to remove")

    def info(self, venv: _venv_option = None):
        """Prints the path for the supplied env

        Parameters
        ----------
        venv
            name of the venv
        """
        self.out(self.vox[venv or ...])

    def upgrade(
        self,
        name: _venv_option = None,
        interpreter: "str|None" = None,
        symlinks=True,
        with_pip=False,
    ):
        """Upgrade the environment directory to use this version
        of Python, assuming Python has been upgraded in-place.

        WARNING: If a virtual environment was created with symlinks or without PIP, you must
        specify these options again on upgrade.

        Parameters
        ----------
        name
            Name or the path to the virtual environment
        interpreter: -p, --interpreter
            Python interpreter used to create the virtual environment.
            Can be configured via the $VOX_DEFAULT_INTERPRETER environment variable.
        symlinks : --copies
            Try to use copies rather than symlinks.
        with_pip : --without-pip, --wp
            Skips installing or upgrading pip in the virtual environment
        """
        venv = self.vox.upgrade(
            name or ..., symlinks=symlinks, with_pip=with_pip, interpreter=interpreter
        )
        self.out(venv)


def _load_xontrib_(xsh: XonshSession, **_):
    xsh.aliases["vox"] = VoxHandler(threadable=False)
