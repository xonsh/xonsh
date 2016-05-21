import os
from os.path import join, basename, exists, expanduser
import venv
import builtins
from shutil import rmtree

import xonsh.tools
from xonsh.platform import ON_POSIX, ON_WINDOWS


class Vox:
    """Vox is a virtual environment manager for xonsh."""

    def __init__(self):
        """Ensure that $VIRTUALENV_HOME is defined and declare the available vox commands"""

        if not builtins.__xonsh_env__.get('VIRTUALENV_HOME'):
            home_path = expanduser('~')

            builtins.__xonsh_env__['VIRTUALENV_HOME'] = join(home_path, '.virtualenvs')

        self.commands = {
            ('new',): self.create_env,
            ('activate', 'workon', 'enter'): self.activate_env,
            ('deactivate', 'exit'): self.deactivate_env,
            ('list', 'ls'): self.list_envs,
            ('remove', 'rm', 'delete', 'del'): self.remove_env,
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

    @staticmethod
    def create_env(name):
        """Create a virtual environment in $VIRTUALENV_HOME with python3's ``venv``.

        Parameters
        ----------
        name : str
            Virtual environment name
        """

        env_path = join(builtins.__xonsh_env__['VIRTUALENV_HOME'], name)

        print('Creating environment...')

        venv.create(env_path, with_pip=True)

        print('Environment "%s" created. Activate it with "vox activate %s".\n' % (name, name))

    def activate_env(self, name):
        """Activate a virtual environment.

        Parameters
        ----------
        name : str
            Virtual environment name
        """

        env_path = join(builtins.__xonsh_env__['VIRTUALENV_HOME'], name)

        if not exists(env_path):
            print('This environment doesn\'t exist. Create it with "vox new %s".\n' % name)
            return None

        if ON_WINDOWS:
            bin_dir = 'Scripts'

        elif ON_POSIX:
            bin_dir = 'bin'

        else:
            print('This OS is not supported.')
            return None

        bin_path = join(env_path, bin_dir)

        if 'VIRTUAL_ENV' in __xonsh_env__:
            self.deactivate_env()

        __xonsh_env__['PATH'].insert(0, bin_path)
        __xonsh_env__['VIRTUAL_ENV'] = env_path

        print('Activated "%s".\n' % name)

    @staticmethod
    def deactivate_env():
        """Deactive the active virtual environment."""

        if 'VIRTUAL_ENV' not in __xonsh_env__:
            print('No environment currently active. Activate one with "vox activate".\n')
            return None

        env_path = __xonsh_env__['VIRTUAL_ENV']

        env_name = basename(env_path)

        if xonsh.tools.ON_WINDOWS:
            bin_dir = 'Scripts'

        elif ON_POSIX:
            bin_dir = 'bin'

        else:
            print('This OS is not supported.')
            return None

        bin_path = join(env_path, bin_dir)

        while bin_path in __xonsh_env__['PATH']:
            __xonsh_env__['PATH'].remove(bin_path)

        __xonsh_env__.pop('VIRTUAL_ENV')

        print('Deactivated "%s".\n' % env_name)

    @staticmethod
    def list_envs():
        """List available virtual environments."""

        venv_home = builtins.__xonsh_env__['VIRTUALENV_HOME']
        try:
            env_dirs = os.listdir(builtins.__xonsh_env__['VIRTUALENV_HOME'])
        except PermissionError:
            print('No permissions on {}'.format(venv_home))
            return None

        if not env_dirs:
            print('No environments available. Create one with "vox new".\n')
            return None

        print('Available environments:')
        print('\n'.join(env_dirs))


    @staticmethod
    def remove_env(name):
        """Remove virtual environment.

        Parameters
        ----------
        name : str
            virtual environment name
        """

        if 'VIRTUAL_ENV' in __xonsh_env__:
            print('This environment is currently active. If you really want to remove it, deactivate it first with "vox deactivate %s".\n' % name)
            return None

        env_path = join(builtins.__xonsh_env__['VIRTUALENV_HOME'], name)

        rmtree(env_path)

        print('Environment "%s" removed.\n' % name)

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

    vox remove (rm, delete, del) <env>
        Remove virtual environment

    vox help (-h, --help)
        Show help
""")
