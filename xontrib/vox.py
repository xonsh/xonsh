"""Python virtual environment manager for xonsh."""
import os
import sys
import venv
import shutil
import builtins
import collections.abc

from xonsh.platform import ON_POSIX, ON_WINDOWS, scandir

VirtualEnvironment = collections.namedtuple('VirtualEnvironment', ['env', 'bin'])

class EnvironmentInUse(Exception): pass

class NoEnvironmentActive(Exception): pass

class Vox(collections.abc.Mapping):
    """API access to Vox and virtual environments, in a dict-like format.

    Makes use of the VirtualEnvironment namedtuple:
    1. ``env``: The full path to the environment
    2. ``bin``: The full path to the bin/Scripts directory of the environment
    """

    def __init__(self):
        if not builtins.__xonsh_env__.get('VIRTUALENV_HOME'):
            home_path = os.path.expanduser('~')
            self.venvdir = os.path.join(home_path, '.virtualenvs')
            builtins.__xonsh_env__['VIRTUALENV_HOME'] = self.venvdir
        else:
            self.venvdir = builtins.__xonsh_env__['VIRTUALENV_HOME']

    def create(self, name):
        """Create a virtual environment in $VIRTUALENV_HOME with python3's ``venv``.

        Parameters
        ----------
        name : str
            Virtual environment name
        """
        env_path = os.path.join(self.venvdir, name)
        venv.create(env_path, with_pip=True)

    @staticmethod
    def _binname():
        if ON_WINDOWS:
            return 'Scripts'
        elif ON_POSIX:
            return 'bin'
        else:
            raise OSError('This OS is not supported.')

    def __getitem__(self, name):
        """Get information about a virtual environment.

        Parameters
        ----------
        name : str or Ellipsis
            Virtual environment name or absolute path. If ... is given, return 
            the current one (throws a KeyError if there isn't one).
        """
        if name is ...:
            env_path = builtins.__xonsh_env__['VIRTUAL_ENV']
        elif os.path.isabs(name):
            env_path = name
        else:
            env_path = os.path.join(self.venvdir, name)
        bin_dir = self._binname()
        bin_path = os.path.join(env_path, bin_dir)
        # Actually check if this is an actual venv or just a organizational directory
        # eg, if 'spam/eggs' is a venv, reject 'spam'
        if not os.path.exists(bin_path):
            raise KeyError()
        return VirtualEnvironment(env_path, bin_path)

    def __iter__(self):
        """List available virtual environments found in $VIRTUALENV_HOME.
        """
        # FIXME: Handle subdirs--this won't discover eg ``spam/eggs``
        for x in scandir(self.venvdir):
            if x.is_dir():
                yield x.name

    def __len__(self):
        """Counts known virtual environments, using the same rules as iter().
        """
        l = 0
        for _ in self:
            l += 1
        return l

    def active(self):
        """Get the name of the active virtual environment.

        You can use this as a key to get further information.

        Returns None if no environment is active.
        """
        if 'VIRTUAL_ENV' not in builtins.__xonsh_env__:
            return
        env_path = builtins.__xonsh_env__['VIRTUAL_ENV']
        if env_path.startswith(self.venvdir):
            name = env_path[len(self.venvdir):]
            if name[0] == '/':
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
        env = builtins.__xonsh_env__
        env_path, bin_path = self[name]
        if 'VIRTUAL_ENV' in env:
            self.deactivate()

        type(self).oldvars = {'PATH': env['PATH']}
        env['PATH'].insert(0, bin_path)
        env['VIRTUAL_ENV'] = env_path
        if 'PYTHONHOME' in env:
            type(self).oldvars['PYTHONHOME'] = env.pop('PYTHONHOME')

    def deactivate(self):
        """
        Deactive the active virtual environment. Returns the name of it.
        """
        env = builtins.__xonsh_env__
        if 'VIRTUAL_ENV' not in env:
            raise NoEnvironmentActive('No environment currently active.')

        env_path, bin_path = self[...]
        env_name = self.active()

        if hasattr(type(self), 'oldvars'):
            for k,v in type(self).oldvars.items():
                env[k] = v
            del type(self).oldvars

        env.pop('VIRTUAL_ENV')

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
                raise EnvironmentInUse('The "%s" environment is currently active.' % name)
        except KeyError:
            # No current venv, ... fails
            pass
        shutil.rmtree(env_path)


class VoxHandler:
    """Vox is a virtual environment manager for xonsh."""

    def __init__(self):
        """Ensure that $VIRTUALENV_HOME is defined and declare the available vox commands"""

        self.vox = Vox()

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
            print('This environment doesn\'t exist. Create it with "vox new %s".\n' % name)
            return None
        else:
            print('Activated "%s".\n' % name)

    def deactivate_env(self):
        """Deactive the active virtual environment."""

        if self.vox.active() is None:
            print('No environment currently active. Activate one with "vox activate".\n')
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
            print('No environments available. Create one with "vox new".\n')
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
            except EnvironmentInUse:
                print('The "%s" environment is currently active. In order to remove it, deactivate it first with "vox deactivate %s".\n' % (name, name),
                      file=sys.stderr)
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


def _vox(args, stdin=None):
    """Runs Vox environment manager."""
    vox = VoxHandler()
    return vox(args, stdin=stdin)

aliases['vox'] = _vox
