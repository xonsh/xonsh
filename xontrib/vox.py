"""Python virtual environment manager for xonsh."""

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

        # todo: completer for interpreter
        create = parser.add_command(
            self.new,
            aliases=["create"],
            args=("name", "interpreter", "system_site_packages", "activate"),
        )

        from xonsh.platform import ON_WINDOWS

        group = create.add_mutually_exclusive_group()
        group.add_argument(
            "--symlinks",
            default=not ON_WINDOWS,
            action="store_true",
            dest="symlinks",
            help="Try to use symlinks rather than copies, "
            "when symlinks are not the default for "
            "the platform.",
        )
        group.add_argument(
            "--copies",
            default=ON_WINDOWS,
            action="store_false",
            dest="symlinks",
            help="Try to use copies rather than symlinks, "
            "even when symlinks are the default for "
            "the platform.",
        )
        create.add_argument(
            "--without-pip",
            dest="with_pip",
            default=True,
            action="store_false",
            help="Skips installing or upgrading pip in the "
            "virtual environment (pip is bootstrapped "
            "by default)",
        )

        parser.add_command(self.activate, aliases=["workon", "enter"])
        parser.add_command(self.deactivate, aliases=["exit"])
        parser.add_command(self.list, aliases=["ls"])
        parser.add_command(self.remove, aliases=["rm", "delete", "del"])
        return parser

    def new(
        self,
        name: xcli.Annotated[str, xcli.Arg(metavar="ENV")],
        interpreter: xcli.Annotated[
            str,
            xcli.Arg("-p", "--interpreter", completer=py_interpreter_path_completer),
        ] = None,
        system_site_packages=False,
        symlinks: bool = False,
        with_pip: bool = True,
        activate=False,
    ):
        """Create a virtual environment in $VIRTUALENV_HOME with python3's ``venv``.

        Parameters
        ----------
        name : str
            Virtual environment name
        interpreter: str
            Python interpreter used to create the virtual environment.
            Can be configured via the $VOX_DEFAULT_INTERPRETER environment variable.
        system_site_packages : --system-site-packages, --ssp
            If True, the system (global) site-packages dir is available to
            created environments.
        symlinks : bool
            If True, attempt to symlink rather than copy files into virtual
            environment.
        with_pip : bool
            If True, ensure pip is installed in the virtual environment. (Default is True)
        activate : -a, --activate
            Activate the newly created virtual environment.
        """
        print("Creating environment...")
        self.vox.create(
            name,
            system_site_packages=system_site_packages,
            symlinks=symlinks,
            with_pip=with_pip,
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
    ):
        """Activate a virtual environment.

        Parameters
        ----------
        name
            The environment to activate.
            ENV can be either a name from the venvs shown by ``vox list``
            or the path to an arbitrary venv
        """

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

    def deactivate(
        self,
        remove=False,
    ):
        """Deactivate the active virtual environment.

        Parameters
        ----------
        remove: -r, --remove
            Remove the virtual environment after leaving it.
        """

        if self.vox.active() is None:
            self.parser.error(
                'No environment currently active. Activate one with "vox activate".\n',
            )
        env_name = self.vox.deactivate()
        if remove:
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
    ):
        """Remove virtual environments.

        Parameters
        ----------
        names
            The environments to remove. ENV can be either a name from the venvs shown by vox
            list or the path to an arbitrary venv
        """
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


XSH.aliases["vox"] = VoxHandler()
