"""Python virtual environment manager for xonsh."""

import sys
import xontrib.voxapi as voxapi
from xonsh.cli_utils import Annotated, Arg, ArgParserAlias, ArgCompleter
from xonsh.built_ins import XSH

__all__ = ()


class VenvNamesCompleter(ArgCompleter):
    def __call__(self, command, alias: "VoxHandler", **_):
        envs = set(alias.vox.keys())
        from xonsh.completers.path import complete_dir

        yield from envs

        paths, _ = complete_dir(command)
        yield from paths


class VoxHandler(ArgParserAlias):
    """Vox is a virtual environment manager for xonsh."""

    def build(self):
        """lazily called during dispatch"""
        self.vox = voxapi.Vox()
        parser = self.create_parser(prog="vox")

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
        parser.add_command(self.help)
        return parser

    def new(
        self,
        name: Annotated[str, Arg(metavar="ENV")],
        interpreter: Annotated[
            str,
            Arg("-p", "--interpreter"),
        ] = None,
        system_site_packages: Annotated[
            bool,
            Arg("--system-site-packages", "--ssp", action="store_true"),
        ] = False,
        symlinks: bool = False,
        with_pip: bool = True,
        activate: Annotated[
            bool,
            Arg("-a", "--activate", action="store_true"),
        ] = False,
    ):
        """
            wraps around vox.create and vox.activate
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
        activate
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
        name: Annotated[
            str, Arg(metavar="ENV", nargs="?", completer=VenvNamesCompleter())
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
            print(
                'This environment doesn\'t exist. Create it with "vox new %s".\n'
                % name,
                file=sys.stderr,
            )
            return None
        else:
            print('Activated "%s".\n' % name)

    def deactivate(
        self,
        remove: Annotated[
            bool,
            Arg("--remove", action="store_true"),
        ] = False,
    ):
        """Deactivate the active virtual environment.

        Parameters
        ----------
        remove
            Remove the virtual environment after leaving it.
        """

        if self.vox.active() is None:
            print(
                'No environment currently active. Activate one with "vox activate".\n',
                file=sys.stderr,
            )
            return None
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
            print("No permissions on VIRTUALENV_HOME")
            return None

        if not envs:
            print(
                'No environments available. Create one with "vox new".\n',
                file=sys.stderr,
            )
            return None

        print("Available environments:")
        print("\n".join(envs))

    def remove(
        self,
        names: Annotated[
            list,
            Arg(metavar="ENV", nargs="+", completer=VenvNamesCompleter()),
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
                print(
                    'The "%s" environment is currently active. '
                    'In order to remove it, deactivate it first with "vox deactivate".\n'
                    % name,
                    file=sys.stderr,
                )
                return
            except KeyError:
                print('"%s" environment doesn\'t exist.\n' % name, file=sys.stderr)
                return
            else:
                print('Environment "%s" removed.' % name)
        print()

    def help(self):
        """Show this help message"""
        self.parser.print_help()


XSH.aliases["vox"] = VoxHandler()
