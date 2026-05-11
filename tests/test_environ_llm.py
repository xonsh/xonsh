import os
import pathlib
import pickle
from collections.abc import Iterable

import pytest

from xonsh.environ import DELETE_VAR, Env, EnvPath, _DeleteVarSentinel
from xonsh.tools import env_path_to_str


def test_env_path_preserves_empty_from_str():
    exp = ["a", "b", "", "c"]
    assert EnvPath(os.pathsep.join(["a", "b", "", "c"])) == exp


def test_env_path_preserves_empty_from_bytes():
    exp = ["a", "b", "", "c"]
    assert EnvPath(os.pathsep.join(["a", "b", "", "c"]).encode("utf-8")) == exp


def test_env_path_preserves_empty_from_iterable():
    class MyIterablePaths(Iterable):
        def __iter__(self):
            return iter(["a", "b", "", pathlib.Path("c")])

    assert EnvPath(MyIterablePaths()) == ["a", "b", "", "c"]


def test_env_path_preserves_leading_empty():
    # POSIX semantics: leading empty in ``MANPATH`` means "system default".
    assert EnvPath(os.pathsep.join(["", "/usr/local/man"])) == ["", "/usr/local/man"]


def test_env_path_round_trip_preserves_empty():
    # Round-trip ``str -> EnvPath -> detype`` keeps the empty entry intact,
    # so subprocesses receive the same value the user set.
    raw = os.pathsep.join(["", "/usr/local/man"])
    assert env_path_to_str(EnvPath(raw)) == raw


def test_env_preserves_empty_for_manpath():
    # ``man``/``info`` interpret an empty entry as "insert the system
    # default list here", so xonsh must not silently drop it.
    raw = os.pathsep + "/home/u/.opam/man"
    env = Env(MANPATH=raw)
    assert env["MANPATH"]._l == ["", "/home/u/.opam/man"]
    assert env.detype()["MANPATH"] == raw


def test_env_preserves_empty_for_pythonpath():
    # An empty entry in ``PYTHONPATH`` means the current directory; if we
    # drop it, ``python -c 'import m'`` stops finding modules in ``$PWD``.
    raw = os.pathsep + "/nope"
    env = Env(PYTHONPATH=raw)
    assert env["PYTHONPATH"]._l == ["", "/nope"]
    assert env.detype()["PYTHONPATH"] == raw


def test_env_windows_path_strips_empty_entries(monkeypatch):
    # ``%PATH%`` on Windows commonly ends with a trailing ``;``. That would
    # otherwise materialize as an empty ("current directory") entry, which
    # is not a documented Windows ``PATH`` semantic. Stripping happens only
    # for ``PATH``, only on Windows. The input uses plain names (no
    # drive-letter colons) so the host's ``os.pathsep`` splits the string
    # unambiguously on any platform.
    import xonsh.environ as xenviron

    monkeypatch.setattr(xenviron, "ON_WINDOWS", True)
    raw = os.pathsep.join(["a", "b", ""])
    env = Env(PATH=raw)
    assert env["PATH"]._l == ["a", "b"]


def test_env_windows_does_not_strip_other_path_vars(monkeypatch):
    # The Windows-only stripping must not bleed into other ``*PATH`` vars.
    import xonsh.environ as xenviron

    monkeypatch.setattr(xenviron, "ON_WINDOWS", True)
    raw = os.pathsep.join(["", "manuals"])
    env = Env(MANPATH=raw)
    assert env["MANPATH"]._l == ["", "manuals"]


# ═══ DELETE_VAR sentinel ═══════════════════════════════════════════════
#
# Covers the sentinel value that masks an environment variable for the
# duration of the surrounding scope: the public surface (direct assign,
# ``swap``, overlays, detype, iteration, ``in``-checks, event firing)
# and the two integration points where the sentinel must be honored —
# the ``spec.env`` override dict used by ``prep_env_subproc`` (inline
# ``$VAR=…`` prefix and ``on_pre_spec_run`` handlers) and the overlay
# dict passed to callable aliases.


# ── singleton & exposure ───────────────────────────────────────────────


def test_delete_var_is_singleton():
    assert DELETE_VAR is _DeleteVarSentinel()
    assert DELETE_VAR is _DeleteVarSentinel()


def test_delete_var_exposed_on_env_class_and_instance():
    assert Env.DELETE_VAR is DELETE_VAR
    env = Env()
    # The attribute path used by `@.env.DELETE_VAR` resolves via class
    # lookup, in parallel with the mapping `__getitem__`.
    assert env.DELETE_VAR is DELETE_VAR


def test_delete_var_repr_is_stable():
    assert repr(DELETE_VAR) == "<XSH.env.DELETE_VAR>"


def test_delete_var_pickle_roundtrip():
    # Spec.env can travel through machinery that pickles things (e.g.
    # multiprocessing); the sentinel must survive a round trip as the
    # same singleton, not become a distinct object that fails `is` checks.
    restored = pickle.loads(pickle.dumps(DELETE_VAR))
    assert restored is DELETE_VAR


# ── direct assignment ─────────────────────────────────────────────────


def test_direct_assign_removes_existing_var():
    env = Env(FOO="bar")
    assert env["FOO"] == "bar"
    env["FOO"] = DELETE_VAR
    assert "FOO" not in env
    with pytest.raises(KeyError):
        env["FOO"]


def test_direct_assign_on_absent_var_is_noop():
    env = Env()
    # Must not raise even though FOO is not a known var: the user's
    # intent ("make sure FOO is absent") is already satisfied.
    env["FOO"] = DELETE_VAR
    assert "FOO" not in env


def test_get_returns_default_for_masked_var():
    env = Env(FOO="bar")
    env["FOO"] = DELETE_VAR
    assert env.get("FOO", "fallback") == "fallback"
    assert env.get("FOO") is None


# ── swap (thread-local) ───────────────────────────────────────────────


def test_swap_with_delete_var_masks_then_restores():
    env = Env(FOO="bar")
    with env.swap(FOO=DELETE_VAR):
        assert "FOO" not in env
        with pytest.raises(KeyError):
            env["FOO"]
    assert env["FOO"] == "bar"


def test_swap_with_delete_var_on_absent_key_stays_absent_after_exit():
    env = Env()
    with env.swap(FOO=DELETE_VAR):
        assert "FOO" not in env
    assert "FOO" not in env


def test_nested_swap_inner_delete_does_not_leak():
    env = Env(FOO="orig")
    with env.swap(FOO="middle"):
        with env.swap(FOO=DELETE_VAR):
            assert "FOO" not in env
        # Inner swap restores middle's value, not the original.
        assert env["FOO"] == "middle"
    assert env["FOO"] == "orig"


def test_swap_with_delete_var_then_inner_override_re_introduces():
    env = Env(FOO="orig")
    with env.swap(FOO=DELETE_VAR):
        assert "FOO" not in env
        with env.swap(FOO="new"):
            assert env["FOO"] == "new"
        assert "FOO" not in env
    assert env["FOO"] == "orig"


# ── overlay parameter (used by callable aliases) ──────────────────────


def test_overlay_delete_var_masks():
    # `Env.swap(overlay=…)` is the API used by ProcProxy to expose an
    # `env` parameter to callable aliases. Putting DELETE_VAR there
    # must mask the underlying var both for reads and for `detype`.
    env = Env(FOO="bar", BAZ="qux")
    overlay = {}
    with env.swap(overlay=overlay):
        overlay["FOO"] = DELETE_VAR
        assert "FOO" not in env
        assert env.get("BAZ") == "qux"
        d = env.detype()
        assert "FOO" not in d
        assert d.get("BAZ") == "qux"
    assert env["FOO"] == "bar"


def test_overlay_value_wins_over_underlying_delete_var():
    # If `swap` masks FOO via DELETE_VAR but a later overlay sets FOO
    # to a real value, that real value wins on read and in detype.
    env = Env(FOO="orig")
    overlay = {"FOO": "new"}
    with env.swap({"FOO": DELETE_VAR}, overlay=overlay):
        assert env["FOO"] == "new"
        assert env.detype().get("FOO") == "new"


# ── detype ────────────────────────────────────────────────────────────


def test_detype_skips_delete_var_keys():
    env = Env(FOO="bar", BAZ="qux")
    with env.swap(FOO=DELETE_VAR):
        d = env.detype()
        assert "FOO" not in d
        assert d.get("BAZ") == "qux"


def test_detype_does_not_leak_sentinel_as_string():
    # Regression guard: a naive implementation would let `ensure_string`
    # render the sentinel as "<XSH.env.DELETE_VAR>" and put that into
    # the env dict passed to Popen.
    env = Env(FOO="bar")
    with env.swap(FOO=DELETE_VAR):
        d = env.detype()
        assert "<XSH.env.DELETE_VAR>" not in d.values()


def test_detype_cache_invalidated_by_delete_var_transitions():
    env = Env(FOO="bar")
    assert env.detype().get("FOO") == "bar"  # primes the cache
    env["FOO"] = DELETE_VAR
    assert "FOO" not in env.detype()
    env["FOO"] = "back"
    assert env.detype().get("FOO") == "back"


# ── iteration & membership ────────────────────────────────────────────


def test_iter_skips_delete_var_keys():
    env = Env(A="1", B="2", C="3")
    with env.swap(B=DELETE_VAR):
        keys = {k for k in env if k in {"A", "B", "C"}}
        assert keys == {"A", "C"}


def test_contains_returns_false_for_delete_var():
    env = Env(FOO="bar")
    with env.swap(FOO=DELETE_VAR):
        assert "FOO" not in env


# ── events ────────────────────────────────────────────────────────────


def test_no_event_fires_on_delete_var_transitions():
    # User-facing handlers should not receive DELETE_VAR as a value:
    # neither when the mask is applied nor when it is lifted.
    import xonsh.environ as environ_mod

    env = Env(FOO="bar")
    seen = []

    def _on_new(name, value, **_):
        seen.append(("new", name, value))

    def _on_change(name, oldvalue, newvalue, **_):
        seen.append(("change", name, oldvalue, newvalue))

    environ_mod.events.on_envvar_new(_on_new)
    environ_mod.events.on_envvar_change(_on_change)
    try:
        with env.swap(FOO=DELETE_VAR):
            pass
        # The transition into the mask and back is invisible to handlers.
        assert seen == [], f"unexpected events fired: {seen}"
    finally:
        environ_mod.events.on_envvar_new.discard(_on_new)
        environ_mod.events.on_envvar_change.discard(_on_change)


# ── integration: SubprocSpec.prep_env_subproc ─────────────────────────


def test_prep_env_subproc_drops_delete_var_key(xession):
    """The dict passed to ``subprocess.Popen(env=…)`` must not contain
    a key that was masked via DELETE_VAR — neither as an empty value nor
    as a stringified sentinel.
    """
    from xonsh.procs.specs import SubprocSpec

    xession.env["MY_TEST_VAR"] = "leaked_value"
    spec = SubprocSpec(
        cmd=["/bin/true"],
        env={"MY_TEST_VAR": DELETE_VAR},
    )
    kwargs = {}
    spec.prep_env_subproc(kwargs)
    assert "MY_TEST_VAR" not in kwargs["env"]
    # The session env still has the original — only this subprocess
    # sees the mask.
    assert xession.env["MY_TEST_VAR"] == "leaked_value"


def test_prep_env_subproc_drops_delete_var_but_keeps_override(xession):
    from xonsh.procs.specs import SubprocSpec

    xession.env["KEEP_ME"] = "session_value"
    xession.env["DROP_ME"] = "leaked"
    spec = SubprocSpec(
        cmd=["/bin/true"],
        env={"KEEP_ME": "override", "DROP_ME": DELETE_VAR},
    )
    kwargs = {}
    spec.prep_env_subproc(kwargs)
    assert kwargs["env"].get("KEEP_ME") == "override"
    assert "DROP_ME" not in kwargs["env"]


def test_on_pre_spec_run_handler_can_mask_via_delete_var(xession):
    """Issue #5782: the handler must be able to remove a variable from
    the subprocess env. Doing so via ``spec.env[name] = DELETE_VAR`` is
    the supported pattern.
    """
    from xonsh.procs.specs import SubprocSpec

    xession.env["FOO"] = "session_value"

    def _mask(spec, **_):
        spec.env = (spec.env or {}) | {"FOO": DELETE_VAR}

    xession.builtins.events.on_pre_spec_run(_mask)
    try:
        spec = SubprocSpec(cmd=["/bin/true"])
        spec._pre_run_event_fire("true")
        kwargs = {}
        spec.prep_env_subproc(kwargs)
        assert "FOO" not in kwargs["env"]
    finally:
        xession.builtins.events.on_pre_spec_run.discard(_mask)


def test_callable_alias_can_mask_via_overlay(xession):
    """The user's example: writing ``env[k] = DELETE_VAR`` from inside a
    callable alias must mask the variable for any read inside the alias
    and for any subprocess spawned from the alias body. ``proxies.py``
    runs the alias inside ``XSH.env.swap(spec.env, overlay=alias_env)``,
    so we reproduce the same overlay protocol here.
    """
    xession.env["HOSTNAME"] = "myhost"
    alias_env = {}
    with xession.env.swap(overlay=alias_env):
        # The alias body would do exactly this:
        alias_env["HOSTNAME"] = DELETE_VAR
        # From inside the alias, the variable is gone.
        assert "HOSTNAME" not in xession.env
        # And `detype` (called by any nested `prep_env_subproc`) omits it.
        assert "HOSTNAME" not in xession.env.detype()
    # Outside the alias scope the original value is intact.
    assert xession.env["HOSTNAME"] == "myhost"
