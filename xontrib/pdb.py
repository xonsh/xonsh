"""Simple built-in debugger. Runs pdb on reception of SIGUSR1 signal."""
import signal

from xonsh.built_ins import XonshSession


def handle_sigusr1(sig, frame):
    print("\nSIGUSR1 signal received. Starting interactive debugger...", flush=True)
    import pdb

    pdb.Pdb().set_trace(frame)


def _load_xontrib_(xsh: XonshSession, **_):
    signal.signal(signal.SIGUSR1, handle_sigusr1)
