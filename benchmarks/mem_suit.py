from contextlib import contextmanager


@contextmanager
def _inp_exit():
    from tempfile import NamedTemporaryFile
    from unittest import mock

    with NamedTemporaryFile(mode="w+") as inp, NamedTemporaryFile(
        mode="w+"
    ) as out, NamedTemporaryFile(mode="w+") as err:
        inp.write("quit\n")
        inp.seek(0)
        with mock.patch("sys.stdin", inp), mock.patch("sys.stdout", out), mock.patch(
            "sys.stderr", err
        ):
            yield inp, out, err

        def read(file):
            file.seek(0)
            return file.read()

        assert "quit" in read(inp)
        # print(f"{read(inp)=}, {read(out)=}, {read(err)=}")


@contextmanager
def _mock_rl():
    from unittest import mock

    from xonsh.readline_shell import ReadlineShell as oldcls

    with _inp_exit() as (inp, out, err):

        class cls(oldcls):
            def __init__(self, **kwargs):
                kwargs["stdin"] = inp
                kwargs["stdout"] = out
                super().__init__(**kwargs)

            def _load_remaining_input_into_queue(self):
                return

        with mock.patch("xonsh.readline_shell.ReadlineShell", cls):
            yield inp, out, err



def script_echo():
    from xonsh.main import main as xmain

    try:
        xmain(["-c", "echo 1"])
    except SystemExit:
        return


def shell_rl():
    with _mock_rl():
        from xonsh.main import main

        try:
            main(["-i", "--shell=rl", "--no-rc"])
        except SystemExit:
            return


def shell_ptk():
    with _inp_exit():
        from xonsh.main import main

        try:
            main(["-i", "--shell=ptk", "--no-rc"])
        except SystemExit:
            return


def peakmem_script():
    script_echo()


def peakmem_interactive_rl():
    shell_rl()


def peakmem_interactive_ptk():
    shell_ptk()


if __name__ == "__main__":
    # change the function to one you want and use pycharm's profile option to run
    import os

    os.environ["XONSH_NO_AMALGAMATE"] = "1"

    # shell_ptk()
    script_echo()
    print("done out")
