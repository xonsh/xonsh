"""Python virtual environment manager for xonsh."""
import os.path
import subprocess
import tempfile
import typing as tp
from pathlib import Path

import xonsh.cli_utils as xcli
import xontrib.voxapi as voxapi
from xonsh.built_ins import XSH


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


class VoxHandler(xcli.ArgParserAlias):
    """Vox is a virtual environment manager for xonsh."""

    def build(self):
        """lazily called during dispatch"""
        self.vox = voxapi.Vox()
        parser = self.create_parser(prog="vox")

        create = parser.add_command(
            self.new,
            aliases=["create"],
        )

        from xonsh.platform import ON_WINDOWS

        group = create.add_mutually_exclusive_group()
        group.add_argument(
            "--symlinks",
            default=not ON_WINDOWS,
            action="store_true",
            dest="_symlinks",
            help="Try to use symlinks rather than copies, "
            "when symlinks are not the default for "
            "the platform.",
        )
        group.add_argument(
            "--copies",
            default=ON_WINDOWS,
            action="store_false",
            dest="_symlinks",
            help="Try to use copies rather than symlinks, "
            "even when symlinks are the default for "
            "the platform.",
        )

        parser.add_command(self.activate, aliases=["workon", "enter"])
        parser.add_command(self.deactivate, aliases=["exit"])
        parser.add_command(self.list, aliases=["ls"])
        parser.add_command(self.remove, aliases=["rm", "delete", "del"])
        parser.add_command(self.info)
        parser.add_command(self.runin)
        parser.add_command(self.runinall)
        return parser

    def new(
        self,
        name: xcli.Annotated[str, xcli.Arg(metavar="ENV")],
        interpreter: xcli.Annotated[
            str, xcli.Arg(completer=py_interpreter_path_completer)
        ] = None,
        system_site_packages=False,
        _symlinks=False,
        without_pip=False,
        activate=False,
        temporary=False,
        packages: xcli.Annotated[tp.Sequence[str], xcli.Arg(nargs="*")] = (),
        requirements: xcli.Annotated[tp.Sequence[str], xcli.Arg(action="append")] = (),
        associate=False,
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
        _symlinks : bool
            If True, attempt to symlink rather than copy files into virtual
            environment.
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
        associate: -l, --link, --associate
            Associate an current directory with the new environment.
        """
        # todo:
        #  2. implement associate
        #  3. -i option to mention package to install
        #  4. -r option to mention requirements.txt

        print("Creating environment...")

        if temporary:
            path = tempfile.mkdtemp(prefix=f"vox-env-{name}")
            name = os.path.join(path, name)

        self.vox.create(
            name,
            system_site_packages=system_site_packages,
            symlinks=_symlinks,
            with_pip=(not without_pip),
            interpreter=interpreter,
        )
        if activate:
            self.vox.activate(name)
            print(f"Environment {name!r} created and activated.\n")
        else:
            print(
                f'Environment {name!r} created. Activate it with "vox activate {name}".\n'
            )

    def activate(
        self,
        name: xcli.Annotated[
            str,
            xcli.Arg(metavar="ENV", nargs="?", completer=venv_names_completer),
        ] = None,
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
        # todo: implement no-cd
        if name is None:
            return self.list()

        try:
            self.vox.activate(name)
        except KeyError:
            self.parser.error(
                f'This environment doesn\'t exist. Create it with "vox new {name}".\n',
            )
            return None
        else:
            print(f'Activated "{name}".\n')

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
            self.parser.error(
                'No environment currently active. Activate one with "vox activate".\n',
            )
        env_name = self.vox.deactivate()
        if remove:
            self.vox.force_removals = force
            del self.vox[env_name]
            print(f'Environment "{env_name}" deactivated and removed.\n')
        else:
            print(f'Environment "{env_name}" deactivated.\n')

    def list(self):
        """List available virtual environments."""

        try:
            envs = sorted(self.vox.keys())
        except PermissionError:
            self.parser.error("No permissions on VIRTUALENV_HOME")
            return None

        if not envs:
            self.parser.error(
                'No environments available. Create one with "vox new".\n',
            )

        print("Available environments:")
        print("\n".join(envs))

    def remove(
        self,
        names: xcli.Annotated[
            list,
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
                self.parser.error(
                    f'The "{name}" environment is currently active. '
                    'In order to remove it, deactivate it first with "vox deactivate".\n',
                )
            except KeyError:
                self.parser.error(f'"{name}" environment doesn\'t exist.\n')
            else:
                print(f'Environment "{name}" removed.')
        print()

    def _in_venv(self):
        return

    def runin(
        self, venv: str, command: xcli.Annotated[tp.List[str], xcli.Arg(nargs="...")]
    ):
        """Run the command in the given environment

        Parameters
        ----------
        venv
            The environment to run the command for
        command
            The actual command to run

        Examples
        --------
          vox runin venv1 flake8 .
        """
        # breakpoint()
        env_dir = self._get_env_dir()
        print(locals())

    def runinall(self, command):
        """Run the command in all environments found under $VIRTUALENV_HOME

        Parameters
        ----------
        command
            The actual command to run
        """
        # todo: implement

    def _sitepackages_dir(self, venv_path: str):
        env_python = self.vox.get_binary_path("python", venv_path)
        if not os.path.exists(env_python):
            self.parser.error("ERROR: no virtualenv active")
            return

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
        venv = venv or "..."
        try:
            env_dir = self.vox[venv].env
        except KeyError:
            # check whether the venv is a valid path to an environment
            if os.path.exists(venv) and os.path.exists(
                self.vox.get_binary_path("python", venv)
            ):
                return venv
            self.parser.error("No virtualenv is found")
            return
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
            print("Enabled global site-packages")
        else:
            with ngsp_file.open("w"):
                print("Disabled global site-packages")

    def project_set(self, venv=None, project_path=None):
        """Bind an existing virtualenv to an existing project.

        Parameters
        ----------
        venv
            Name of the virtualenv under $VIRTUALENV_HOME, while default being currently active venv.
        project_path
            Path to the project, while default being current directory.
        """
        # todo

    def project_get(self, venv=None):
        """Return a virtualenv's project directory.

        Parameters
        ----------
        venv
            Name of the virtualenv under $VIRTUALENV_HOME, while default being currently active venv.
        """

    def wipe(self, venv=None):
        """Remove all installed packages from the current (or supplied) env.

        Parameters
        ----------
        venv
            name of the venv
        """
        env_dir = self._get_env_dir(venv)
        pip_bin = self.vox.get_binary_path("pip", env_dir)
        all_pkgs = set(
            subprocess.check_output([pip_bin, "freeze", "--local"])
            .decode()
            .splitlines()
        )
        pkgs = set(p for p in all_pkgs if len(p.split("==")) == 2)
        ignored = sorted(all_pkgs - pkgs)
        to_remove = set(p.split("==")[0] for p in pkgs)
        if to_remove:
            print("Ignoring:\n %s" % "\n ".join(ignored))
            print("Uninstalling packages:\n %s" % "\n ".join(to_remove))
            return subprocess.run([pip_bin, "uninstall", "-y", *to_remove])
        else:
            print("Nothing to remove")

    def info(self, venv=None):
        """Prints the path for the supplied env

        Parameters
        ----------
        venv
            name of the venv
        """
        print(self.vox[venv or ...])


XSH.aliases["vox"] = VoxHandler()
