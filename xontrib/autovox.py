"""
Manages automatic activation of virtual environments.

This coordinates multiple automatic vox policies and deals with some of the
mechanics of venv searching and chdir handling.

This provides no interface for end users.

Developers should look at XSH.builtins.events.autovox_policy
"""
import itertools
import warnings
from pathlib import Path

import xontrib.voxapi as voxapi
from xonsh.built_ins import XSH, XonshSession

__all__ = ()


def autovox_policy(path: "Path") -> "str|Path|None":
    """
    Register a policy with autovox.

    A policy is a function that takes a Path and returns the venv associated with it,
    if any.

    NOTE: The policy should only return a venv for this path exactly, not for
    parent paths. Parent walking is handled by autovox so that all policies can
    be queried at each level.
    """


class MultipleVenvsWarning(RuntimeWarning):
    pass


def get_venv(vox, dirpath):
    # Search up the directory tree until a venv is found, or none
    for path in itertools.chain((dirpath,), dirpath.parents):
        venvs = [
            vox[p]
            for p in XSH.builtins.events.autovox_policy.fire(path=path)
            if p is not None and p in vox  # Filter out venvs that don't exist
        ]
        if len(venvs) == 0:
            continue
        else:
            if len(venvs) > 1:
                warnings.warn(
                    MultipleVenvsWarning(
                        "Found {numvenvs} venvs for {path}; using the first".format(
                            numvenvs=len(venvs), path=path
                        )
                    )
                )
            return venvs[0]


def check_for_new_venv(curdir, olddir):
    vox = voxapi.Vox()
    if olddir is ... or olddir is None:
        try:
            oldve = vox[...]
        except KeyError:
            oldve = None
    else:
        oldve = get_venv(vox, olddir)
    newve = get_venv(vox, curdir)

    if oldve != newve:
        if newve is None:
            vox.deactivate()
        else:
            vox.activate(newve.env)


# Core mechanism: Check for venv when the current directory changes


def cd_handler(newdir, olddir, **_):
    check_for_new_venv(Path(newdir), Path(olddir))


# Recalculate when venvs are created or destroyed


def create_handler(**_):
    check_for_new_venv(Path.cwd(), ...)


def destroy_handler(**_):
    check_for_new_venv(Path.cwd(), ...)


# Initial activation before first prompt


def load_handler(**_):
    check_for_new_venv(Path.cwd(), None)


def _load_xontrib_(xsh: XonshSession, **_):
    xsh.builtins.events.register(autovox_policy)
    xsh.builtins.events.on_chdir(cd_handler)
    xsh.builtins.events.vox_on_create(create_handler)
    xsh.builtins.events.vox_on_destroy(destroy_handler)
    xsh.builtins.events.on_post_init(load_handler)
