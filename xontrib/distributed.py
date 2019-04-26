"""Hooks for the distributed parallel computing library."""
from xonsh.contexts import Functor

__all__ = "DSubmitter", "dsubmit"


def dworker(args, stdin=None):
    """Programmatic access to the dworker utility, to allow launching
    workers that also have access to xonsh builtins.
    """
    from distributed.cli import dworker

    dworker.main.main(args=args, prog_name="dworker", standalone_mode=False)


aliases["dworker"] = dworker


class DSubmitter(Functor):
    """Context manager for submitting distributed jobs."""

    def __init__(self, executor, **kwargs):
        """
        Parameters
        ----------
        executor : distributed.Executor
            The executor to submit to.
        kwargs : optional
            All other kwargs are passed up to superclasses init.
        """
        super().__init__(**kwargs)
        self.executor = executor
        self.future = None

    def __enter__(self):
        super().__enter__()
        self.future = None
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        res = super().__exit__(exc_type, exc_value, traceback)
        if not res:
            return res
        self.future = self.executor.submit(self.func)
        return res


def dsubmit(*a, args=(), kwargs=None, rtn="", **kw):
    """Returns a distributed submission context manager, DSubmitter(),
    with a new executor instance.

    Parameters
    ----------
    args : Sequence of str, optional
        A tuple of argument names for DSubmitter.
    kwargs : Mapping of str to values or list of item tuples, optional
        Keyword argument names and values for DSubmitter.
    rtn : str, optional
        Name of object to return for DSubmitter.
    a, kw : Sequence and Mapping
        All other arguments and keyword arguments are used to construct
        the executor instance.

    Returns
    -------
    dsub : DSubmitter
        An instance of the DSubmitter context manager.
    """
    from distributed import Executor

    e = Executor(*a, **kw)
    dsub = DSubmitter(e, args=args, kwargs=kwargs, rtn=rtn)
    return dsub
