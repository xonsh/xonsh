import tempfile

from xonsh.lib.os import indir
from xonsh.lib.subprocess import run, check_call, check_output


def test_run():
    with tempfile.TemporaryDirectory() as tmpdir:
        with indir(tmpdir):
            run(['touch', 'hello.txt'])
            assert 'hello.txt' in g`*.txt`
            rm hello.txt
            mkdir tst_dir
            run(['touch', 'hello.txt'], cwd='tst_dir')
            assert 'tst_dir/hello.txt' in g`tst_dir/*.txt`


def test_check_call():
    with tempfile.TemporaryDirectory() as tmpdir:
        with indir(tmpdir):
            check_call(['touch', 'hello.txt'])
            assert 'hello.txt' in g`*.txt`
            rm hello.txt
            mkdir tst_dir
            check_call(['touch', 'hello.txt'], cwd='tst_dir')
            assert 'tst_dir/hello.txt' in g`tst_dir/*.txt`


def test_check_output():
    with tempfile.TemporaryDirectory() as tmpdir:
        with indir(tmpdir):
            check_call(['touch', 'hello.txt'])
            assert 'hello.txt' in g`*.txt`
            rm hello.txt
            mkdir tst_dir
            p = check_output(['touch', 'hello.txt'], cwd='tst_dir')
            assert p.decode('utf-8') == ''
            assert 'tst_dir/hello.txt' in g`tst_dir/*.txt`
