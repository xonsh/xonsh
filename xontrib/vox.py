"""Python virtual environment manager for xonsh."""

import sys as _sys
import xontrib.voxapi as _voxapi

class _VoxHandler:
    """Vox is a virtual environment manager for xonsh."""

    def __init__(self):
        """Ensure that $VIRTUALENV_HOME is defined and declare the available vox commands"""

        self.vox = _voxapi.Vox()

        self.commands = {
            ('new',): self.create_env,
            ('activate', 'workon', 'enter'): self.activate_env,
            ('deactivate', 'exit'): self.deactivate_env,
            ('list', 'ls'): self.list_envs,
            ('remove', 'rm', 'delete', 'del'): self.remove_envs,
            ('help', '-h', '--help'): self.show_help
        }

    def __call__(self, args, stdin=None):
        """Call the right handler method for a given command."""

        if not args:
            self.show_help()
            return None

        command_name, params = args[0], args[1:]

        try:
            command = [
                self.commands[aliases] for aliases in self.commands
                if command_name in aliases
            ][0]

            command(*params)

        except IndexError:
            print('Command "%s" doesn\'t exist.\n' % command_name)
            self.print_commands()

    def create_env(self, name):
        """Create a virtual environment in $VIRTUALENV_HOME with python3's ``venv``.

        Parameters
        ----------
        name : str
            Virtual environment name
        """
        print('Creating environment...')
        self.vox.create(name)
        msg = 'Environment {0!r} created. Activate it with "vox activate {0}".\n'
        print(msg.format(name))

    def activate_env(self, name):
        """Activate a virtual environment.

        Parameters
        ----------
        name : str
            Virtual environment name
        """

        try:
            self.vox.activate(name)
        except KeyError:
            print('This environment doesn\'t exist. Create it with "vox new %s".\n' % name, file=_sys.stderr)
            return None
        else:
            print('Activated "%s".\n' % name)

    def deactivate_env(self):
        """Deactive the active virtual environment."""

        if self.vox.active() is None:
            print('No environment currently active. Activate one with "vox activate".\n', file=_sys.stderr)
            return None
        env_name = self.vox.deactivate()
        print('Deactivated "%s".\n' % env_name)

    def list_envs(self):
        """List available virtual environments."""

        try:
            envs = list(self.vox.keys())
        except PermissionError:
            print('No permissions on VIRTUALENV_HOME'.format(venv_home))
            return None

        if not envs:
            print('No environments available. Create one with "vox new".\n', file=_sys.stderr)
            return None

        print('Available environments:')
        print('\n'.join(envs))


    def remove_envs(self, *names):
        """Remove virtual environments.

        Parameters
        ----------
        names : list
            list of virtual environment names
        """
        for name in names:
            try:
                del self.vox[name]
            except _voxapi.EnvironmentInUse:
                print('The "%s" environment is currently active. In order to remove it, deactivate it first with "vox deactivate %s".\n' % (name, name),
                      file=_sys.stderr)
                return
            else:
                print('Environment "%s" removed.' % name)
        print()

    def show_help(self):
        """Show help."""

        print(self.__doc__, '\n')
        self.print_commands()

    @staticmethod
    def print_commands():
        """Print available vox commands."""

        print("""Available commands:
    vox new <env>
        Create new virtual environment in $VIRTUALENV_HOME

    vox activate (workon, enter) <env>
        Activate virtual environment

    vox deactivate (exit)
        Deactivate current virtual environment

    vox list (ls)
        List all available environments

    vox remove (rm, delete, del) <env> <env2> ...
        Remove virtual environments

    vox help (-h, --help)
        Show help
""")

    @classmethod
    def handle(cls, args, stdin=None):
        """Runs Vox environment manager."""
        vox = cls()
        return vox(args, stdin=stdin)

aliases['vox'] = _VoxHandler.handle
