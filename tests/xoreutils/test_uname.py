import io
import sys
import platform
import pytest

from xonsh.xoreutils import uname
from xonsh.platform import DEFAULT_ENCODING


@pytest.fixture
def uname_env_fixture(xonsh_builtins):
    with xonsh_builtins.__xonsh__.env.swap(
            XONSH_ENCODING=DEFAULT_ENCODING, XONSH_ENCODING_ERRORS="surrogateescape"
    ):
        yield xonsh_builtins


class TestUname:
    def setup(self):
        if hasattr(self, 'stdout'):
            self.stdout.flush()
        if hasattr(self, 'stdin'):
            self.stdin.flush()
        if hasattr(self, 'stderr'):
            self.stderr.flush()
        self.stdin = io.StringIO()
        self.stdin.flush()
        self.stdout_buf = io.BytesIO()
        self.stderr_buf = io.BytesIO()
        self.stdout = io.TextIOWrapper(self.stdout_buf)
        self.stderr = io.TextIOWrapper(self.stderr_buf)

    def test_uname_without_args(self, uname_env_fixture):
        uname.uname([], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(platform.uname().system), DEFAULT_ENCODING)

    def test_uname_a(self, uname_env_fixture):
        uname.uname(['-a'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        processor = platform.uname().processor
        if processor == '':
            processor = 'unknown'

        assert self.stdout_buf.getvalue() == bytes('{0} {1} {2} {3} {4} {7}\n'.format(
            platform.uname().system,
            platform.uname().node,
            platform.uname().release,
            platform.uname().version,
            platform.uname().machine,
            processor,
            'unknown',
            sys.platform
        ), DEFAULT_ENCODING)

    def test_uname_all(self, uname_env_fixture):
        uname.uname(['--all'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        processor = platform.uname().processor
        if processor == '':
            processor = 'unknown'

        assert self.stdout_buf.getvalue() == bytes('{0} {1} {2} {3} {4} {7}\n'.format(
            platform.uname().system,
            platform.uname().node,
            platform.uname().release,
            platform.uname().version,
            platform.uname().machine,
            processor,
            'unknown',
            sys.platform
        ), DEFAULT_ENCODING)

    def test_uname_kernel_s(self, uname_env_fixture):
        uname.uname(['-s'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(platform.uname().system), DEFAULT_ENCODING)

    def test_uname_kernel_name(self, uname_env_fixture):
        uname.uname(['--kernel-name'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(platform.uname().system), DEFAULT_ENCODING)

    def test_uname_n(self, uname_env_fixture):
        uname.uname(['-n'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(platform.uname().node), DEFAULT_ENCODING)

    def test_uname_nodename(self, uname_env_fixture):
        uname.uname(['--nodename'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(platform.uname().node), DEFAULT_ENCODING)

    def test_uname_r(self, uname_env_fixture):
        uname.uname(['-r'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(platform.uname().release), DEFAULT_ENCODING)

    def test_uname_kernel_release(self, uname_env_fixture):
        uname.uname(['--kernel-release'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(platform.uname().release), DEFAULT_ENCODING)

    def test_uname_v(self, uname_env_fixture):
        uname.uname(['-v'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(platform.uname().version), DEFAULT_ENCODING)

    def test_uname_kernel_version(self, uname_env_fixture):
        uname.uname(['--kernel-version'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(platform.uname().version), DEFAULT_ENCODING)

    def test_uname_m(self, uname_env_fixture):
        uname.uname(['-m'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(platform.uname().machine), DEFAULT_ENCODING)

    def test_uname_machine(self, uname_env_fixture):
        uname.uname(['--machine'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(platform.uname().machine), DEFAULT_ENCODING)

    def test_uname_p(self, uname_env_fixture):
        uname.uname(['-p'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        processor = platform.uname().processor
        if processor == '':
            processor = 'unknown'

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(processor), DEFAULT_ENCODING)

    def test_uname_processor(self, uname_env_fixture):
        uname.uname(['--processor'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        processor = platform.uname().processor
        if processor == '':
            processor = 'unknown'

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(processor), DEFAULT_ENCODING)

    def test_uname_i(self, uname_env_fixture):
        uname.uname(['-i'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format('unknown'), DEFAULT_ENCODING)

    def test_uname_hardware_platform(self, uname_env_fixture):
        uname.uname(['--hardware-platform'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format('unknown'), DEFAULT_ENCODING)

    def test_uname_o(self, uname_env_fixture):
        uname.uname(['-o'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(sys.platform), DEFAULT_ENCODING)

    def test_uname_operating_system(self, uname_env_fixture):
        uname.uname(['--operating-system'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(sys.platform), DEFAULT_ENCODING)

    def test_uname_help(self, uname_env_fixture):
        uname.uname(['--help'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0}\n'.format(
            "This version of cat was written in Python for the xonsh project: http://xon.sh\n"
            "Based on cat from GNU coreutils: http://www.gnu.org/software/coreutils/\n"
            "\n"
            "Usage: uname [OPTION]...\n"
            "Print certain system information.  With no OPTION, same as -s.\n"
            "\n"
            "  -a, --all                print all information, in the following order,\n"
            "                             except omit -p and -i if unknown:\n"
            "  -s, --kernel-name        print the kernel name\n"
            "  -n, --nodename           print the network node hostname\n"
            "  -r, --kernel-release     print the kernel release\n"
            "  -v, --kernel-version     print the kernel version\n"
            "  -m, --machine            print the machine hardware name\n"
            "  -p, --processor          print the processor type (non-portable)\n"
            "  -i, --hardware-platform  print the hardware platform (non-portable)\n"
            "  -o, --operating-system   print the operating system\n"
            "      --help     display this help and exit\n"
            "      --version  output version information and exit"
        ), DEFAULT_ENCODING)

    def test_uname_version(self, uname_env_fixture):
        uname.uname(['--version'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        assert self.stdout_buf.getvalue() == bytes('{0} {1}\n'.format(
            "uname",
            "0.1"
        ), DEFAULT_ENCODING)

    def test_uname_everything(self, uname_env_fixture):
        uname.uname(['-s', '-n', '-r', '-v', '-m', '-p', '-i', '-o'], self.stdin, self.stdout, self.stderr)
        self.stdout.flush()

        processor = platform.uname().processor
        if processor == '':
            processor = 'unknown'

        assert self.stdout_buf.getvalue() == bytes('{0} {1} {2} {3} {4} {5} {6} {7}\n'.format(
            platform.uname().system,
            platform.uname().node,
            platform.uname().release,
            platform.uname().version,
            platform.uname().machine,
            processor,
            'unknown',
            sys.platform
        ), DEFAULT_ENCODING)
