
def time_script():
    import subprocess as sp

    sp.run(["xonsh", "-c", "echo 1"])


def _shell_process(backend:str):
    import os
    import pty
    import subprocess
    master_fd, slave_fd = pty.openpty()

    proc = subprocess.Popen(["xonsh", "--interactive", "--no-rc", f"--shell={backend}"],
                               stdin=slave_fd,
                               stdout=slave_fd,
                               stderr=slave_fd)

    print(os.read(master_fd, 1024))

    os.write(master_fd, b"echo 1\n")
    output = os.read(master_fd, 1024)
    print(output)
    proc.terminate()

def time_interactive_rl():
    _shell_process("rl")


def time_interactive_ptk():
    _shell_process("ptk")


if __name__ == '__main__':
    # time_interactive_rl()
    time_interactive_ptk()
