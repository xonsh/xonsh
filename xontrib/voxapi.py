"""API for Vox, the Python virtual environment manager for xonsh."""
import os
import venv
import shutil
import builtins
import collections.abc

from xonsh.platform import ON_POSIX, ON_WINDOWS, scandir


VirtualEnvironment = collections.namedtuple('VirtualEnvironment', ['env', 'bin'])


class EnvironmentInUse(Exception):
    pass


class NoEnvironmentActive(Exception):
    pass


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

    def create(self, name, *, system_site_packages=False, symlinks=False,
               with_pip=True):
        """Create a virtual environment in $VIRTUALENV_HOME with python3's ``venv``.

        Parameters
        ----------
        name : str
            Virtual environment name
        system_site_packages : bool
            If True, the system (global) site-packages dir is available to
            created environments.
        symlinks : bool
            If True, attempt to symlink rather than copy files into virtual
            environment.
        with_pip : bool
            If True, ensure pip is installed in the virtual environment. (Default is True)
        """
        # NOTE: clear=True is the same as delete then create.
        # NOTE: upgrade=True is its own method
        env_path = os.path.join(self.venvdir, name)
        venv.create(
            env_path,
            system_site_packages=system_site_packages, symlinks=symlinks,
            with_pip=with_pip)

    def upgrade(self, name, *, symlinks=False, with_pip=True):
        """Create a virtual environment in $VIRTUALENV_HOME with python3's ``venv``.

        WARNING: If a virtual environment was created with symlinks or without PIP, you must
        specify these options again on upgrade.

        Parameters
        ----------
        name : str
            Virtual environment name
        symlinks : bool
            If True, attempt to symlink rather than copy files into virtual
            environment.
        with_pip : bool
            If True, ensure pip is installed in the virtual environment.
        """
        # venv doesn't reload this, so we have to do it ourselves.
        # Is there a bug for this in Python? There should be.
        env_path, bin_path = self[name]
        cfgfile = os.path.join(env_path, 'pyvenv.cfg')
        cfgops = {}
        with open(cfgfile) as cfgfile:
            for l in cfgfile:
                l = l.strip()
                if '=' not in l:
                    continue
                k, v = l.split('=', 1)
                cfgops[k.strip()] = v.strip()
        flags = {
            'system_site_packages': cfgops['include-system-site-packages'] == 'true',
            'symlinks': symlinks,
            'with_pip': with_pip,
        }
        # END things we shouldn't be doing.

        # Ok, do what we came here to do.
        venv.create(env_path, upgrade=True, **flags)

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

        type(self).oldvars = {'PATH': list(env['PATH'])}
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
            for k, v in type(self).oldvars.items():
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
