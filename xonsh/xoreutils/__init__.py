from xonsh.xoreutils.pwd import pwd
from xonsh.xoreutils.cat import cat
from xonsh.xoreutils.tty import tty
from xonsh.xoreutils.tee import tee
from xonsh.xoreutils.yes import yes
from xonsh.xoreutils.echo import echo
from xonsh.xoreutils.which import which

all_builtin_commands = {
    'cat': cat,
    'pwd': pwd,
    'tee': tee,
    'tty': tty,
    'yes': yes,
    'echo': echo,
    'which': which,
}
