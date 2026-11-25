import io
import os

import pytest

from xonsh.platform import DEFAULT_ENCODING
from xonsh.xoreutils import cat


@pytest.fixture
def cat_env_fixture(xession):
    with xession.env.swap(
        XONSH_ENCODING=DEFAULT_ENCODING, XONSH_ENCODING_ERRORS="surrogateescape"
    ):
        yield xession


class CatLimitedBuffer(io.BytesIO):
    """
    This object cause KeyboardInterrupt when reached expected buffer size
    """

    def __init__(self, limit=500, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.limited_size = limit
        self.already_raised = False

    def write(self, *args, **kwargs):
        super().write(*args, **kwargs)
        if not self.already_raised and self.tell() >= self.limited_size:
            self.already_raised = True
            raise KeyboardInterrupt()


class TestCatLimitedBuffer:
    def test_write_buffer_correctly(self):
        buf = CatLimitedBuffer(limit=500)
        buf.write(b"0" * 499)
        assert buf.getvalue() == b"0" * 499

    def test_raise_keyboardinterrupt_when_reached(self):
        buf = CatLimitedBuffer(limit=500)
        buf.write(b"0" * 499)
        with pytest.raises(KeyboardInterrupt):
            buf.write(b"1")

    def test_raise_allow_write_over_limit(self):
        buf = CatLimitedBuffer(limit=500)
        buf.write(b"0" * 400)
        with pytest.raises(KeyboardInterrupt):
            buf.write(b"1" * 200)

        assert buf.getvalue() == (b"0" * 400 + b"1" * 200)

    def test_not_raise_twice_time(self):
        buf = CatLimitedBuffer(limit=500)
        with pytest.raises(KeyboardInterrupt):
            buf.write(b"1" * 1000)
        try:
            buf.write(b"2")
        except KeyboardInterrupt:
            pytest.fail("Unexpected KeyboardInterrupt")


class TestCat:
    tempfile = None

    def setup_method(self, _method):
        import tempfile

        tmpfile = tempfile.mkstemp()
        self.tempfile = tmpfile[1]
        os.close(tmpfile[0])

    def teardown_method(self, _method):
        os.remove(self.tempfile)

    @pytest.mark.parametrize(
        "content",
        [
            "this is a content\nfor testing xoreutil's cat",
            "this is a content withe \\n\nfor testing xoreutil's cat\n",
            "",
        ],
    )
    def test_cat_single_file_work_exist_content(self, cat_env_fixture, content):
        with open(self.tempfile, "w") as f:
            f.write(content)
        expected_content = content.replace("\n", os.linesep)

        stdin = io.StringIO()
        stdout_buf = io.BytesIO()
        stderr_buf = io.BytesIO()
        stdout = io.TextIOWrapper(stdout_buf)
        stderr = io.TextIOWrapper(stderr_buf)
        opts = cat._cat_parse_args([])
        # Longer timeout to avoid race on slow CI machines
        cat._cat_single_file(opts, self.tempfile, stdin, stdout, stderr, read_timeout=2)
        stdout.flush()
        stderr.flush()
        assert stdout_buf.getvalue() == bytes(expected_content, "utf-8")
        assert stderr_buf.getvalue() == b""

    @pytest.mark.skipif(
        not os.path.exists("/dev/urandom"), reason="/dev/urandom doesn't exists"
    )
    def test_cat_dev_urandom(self, cat_env_fixture):
        """
        test of cat (pseudo) device.
        """
        stdin = io.StringIO()
        stdout_buf = CatLimitedBuffer(limit=500)
        stderr_buf = io.BytesIO()
        stdout = io.TextIOWrapper(stdout_buf)
        stderr = io.TextIOWrapper(stderr_buf)
        opts = cat._cat_parse_args([])
        cat._cat_single_file(opts, "/dev/urandom", stdin, stdout, stderr)
        stdout.flush()
        stderr.flush()
        assert len(stdout_buf.getvalue()) >= 500


def _cat_output(args, fname, stdin):
    stdout_buf = io.BytesIO()
    stdout = io.TextIOWrapper(stdout_buf)
    stderr = io.TextIOWrapper(io.BytesIO())
    opts = cat._cat_parse_args(args)
    # Longer timeout to avoid race on slow CI machines
    cat._cat_single_file(opts, fname, stdin, stdout, stderr, read_timeout=2)
    stdout.flush()
    return stdout_buf.getvalue().decode()


@pytest.mark.parametrize(
    "args, content, expected",
    [
        (["-n"], "a\nb\n", "     1 a\n     2 b\n"),
        (["-n"], "a\nb", "     1 a\n     2 b"),
        (["-b"], "a\n\nb\n", "     1 a\n\n     2 b\n"),
        (["-E"], "a\nb\n", "a$\nb$\n"),
        (["-s"], "a\n\n\n\nb\n", "a\n\nb\n"),
        # spans several reads of the 1 kb file reader
        (["-n"], f"{'x' * 3000}\ny\n", f"     1 {'x' * 3000}\n     2 y\n"),
    ],
)
def test_cat_line_options_apply_to_each_line(
    cat_env_fixture, tmp_path, args, content, expected
):
    path = tmp_path / "file.txt"
    path.write_bytes(content.replace("\n", os.linesep).encode())

    output = _cat_output(args, str(path), io.StringIO())

    assert output == expected.replace("\n", os.linesep)


def test_cat_number_does_not_split_long_stdin_line(cat_env_fixture):
    stdin = io.StringIO(f"{'x' * 100}\ny\n")

    output = _cat_output(["-n"], "-", stdin)

    assert output == f"     1 {'x' * 100}\n     2 y\n"
