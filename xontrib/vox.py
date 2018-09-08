"""Python virtual environment manager for xonsh."""

import sys
import xontrib.voxapi as voxapi
import xonsh.lazyasd as lazyasd

__all__ = ()


class VoxHandler:
    """Vox is a virtual environment manager for xonsh."""

    def parser():
        from argparse import ArgumentParser
        parser = ArgumentParser(prog='vox', description=__doc__)
        subparsers = parser.add_subparsers(dest='command')

        create = subparsers.add_parser(
            'new', aliases=['create'],
            help='Create a new virtual environment'
        )
        create.add_argument('name', metavar='ENV',
                            help='The environments to create')

        create.add_argument('--system-site-packages', default=False,
                            action='store_true', dest='system_site_packages',
                            help='Give the virtual environment access to the '
                                 'system site-packages dir.')

        from xonsh.platform import ON_WINDOWS
        group = create.add_mutually_exclusive_group()
        group.add_argument('--symlinks', default=not ON_WINDOWS,
                           action='store_true', dest='symlinks',
                           help='Try to use symlinks rather than copies, '
                                'when symlinks are not the default for '
                                'the platform.')
        group.add_argument('--copies', default=ON_WINDOWS,
                           action='store_false', dest='symlinks',
                           help='Try to use copies rather than symlinks, '
                                'even when symlinks are the default for '
                                'the platform.')
        create.add_argument('--without-pip', dest='with_pip',
                            default=True, action='store_false',
                            help='Skips installing or upgrading pip in the '
                                 'virtual environment (pip is bootstrapped '
                                 'by default)')

        activate = subparsers.add_parser(
            'activate', aliases=['workon', 'enter'],
            help='Activate virtual environment'
        )
        activate.add_argument('name', metavar='ENV',
                              help='The environment to activate')
        subparsers.add_parser('deactivate', aliases=['exit'], help='Deactivate current virtual environment')
        subparsers.add_parser('list', aliases=['ls'], help='List all available environments')
        remove = subparsers.add_parser('remove', aliases=['rm', 'delete', 'del'], help='Remove virtual environment')
        remove.add_argument('names', metavar='ENV', nargs='+',
                            help='The environments to remove')
        subparsers.add_parser('help', help='Show this help message')
        return parser

    parser = lazyasd.LazyObject(parser, locals(), 'parser')

    aliases = {
        'create': 'new',
        'workon': 'activate',
        'enter': 'activate',
        'exit': 'deactivate',
        'ls': 'list',
        'rm': 'remove',
        'delete': 'remove',
        'del': 'remove',
    }

    def __init__(self):
        self.vox = voxapi.Vox()

    def __call__(self, args, stdin=None):
        """Call the right handler method for a given command."""

        args = self.parser.parse_args(args)
        cmd = self.aliases.get(args.command, args.command)
        if cmd is None:
            self.parser.print_usage()
        else:
            getattr(self, 'cmd_' + cmd)(args, stdin)

    def cmd_new(self, args, stdin=None):
        """Create a virtual environment in $VIRTUALENV_HOME with python3's ``venv``.
        """
        print('Creating environment...')
        self.vox.create(args.name,
                        system_site_packages=args.system_site_packages,
                        symlinks=args.symlinks,
                        with_pip=args.with_pip)
        msg = 'Environment {0!r} created. Activate it with "vox activate {0}".\n'
        print(msg.format(args.name))

    def cmd_activate(self, args, stdin=None):
        """Activate a virtual environment.
        """

        try:
            self.vox.activate(args.name)
        except KeyError:
            print('This environment doesn\'t exist. Create it with "vox new %s".\n' % args.name, file=sys.stderr)
            return None
        else:
            print('Activated "%s".\n' % args.name)

    def cmd_deactivate(self, args, stdin=None):
        """Deactivate the active virtual environment."""

        if self.vox.active() is None:
            print('No environment currently active. Activate one with "vox activate".\n', file=sys.stderr)
            return None
        env_name = self.vox.deactivate()
        print('Deactivated "%s".\n' % env_name)

    def cmd_list(self, args, stdin=None):
        """List available virtual environments."""

        try:
            envs = sorted(self.vox.keys())
        except PermissionError:
            print('No permissions on VIRTUALENV_HOME')
            return None

        if not envs:
            print('No environments available. Create one with "vox new".\n', file=sys.stderr)
            return None

        print('Available environments:')
        print('\n'.join(envs))

    def cmd_remove(self, args, stdin=None):
        """Remove virtual environments.
        """
        for name in args.names:
            try:
                del self.vox[name]
            except voxapi.EnvironmentInUse:
                print('The "%s" environment is currently active. In order to remove it, deactivate it first with "vox deactivate %s".\n' % (name, name),
                      file=sys.stderr)
                return
            else:
                print('Environment "%s" removed.' % name)
        print()

    def cmd_help(self, args, stdin=None):
        self.parser.print_help()

    @classmethod
    def handle(cls, args, stdin=None):
        """Runs Vox environment manager."""
        vox = cls()
        return vox(args, stdin=stdin)


aliases['vox'] = VoxHandler.handle
