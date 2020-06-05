"""Simple built-in debugger. Runs pdb on reception of SIGUSR1 signal."""
import signal

__all__ = ()


def handle_sigusr1(sig, frame):
    print("\nSIGUSR1 signal received. Starting interactive debugger...", flush=True)
    import pdb

    pdb.Pdb().set_trace(frame)


signal.signal(signal.SIGUSR1, handle_sigusr1)
