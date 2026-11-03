"""Native asynchronous prompt fallback coverage."""

import concurrent.futures
import threading

import pytest
from prompt_toolkit.formatted_text import to_formatted_text

from xonsh.built_ins import XSH
from xonsh.prompt.base import BasePromptField
from xonsh.shells.ptk_shell.updator import AsyncPrompt, Executor, PromptUpdator
from xonsh.style_tools import style_as_faded


def _fallback_text(tokens):
    return "".join(item[1] for item in to_formatted_text(tokens))


@pytest.fixture
def _fallback_runtime(ptk_shell, monkeypatch):
    _, _, shell = ptk_shell
    # Load style annotations before observing Timer construction.
    _ = shell.styler
    env = XSH.env
    env["PROMPT_FIELDS"].reset()
    env.update(ENABLE_ASYNC_PROMPT=True, ASYNC_INVALIDATE_INTERVAL=0)
    # Original-source RED must reach rendering before registration exists.
    env["XONSH_ASYNC_PROMPT_FALLBACKS"] = {}
    releases, timers, futures, prompts, threads = [], [], [], [], []
    original_timer = threading.Timer

    errors = []

    def timer(interval, function, args=None, kwargs=None):
        def observe_timer():
            try:
                function(*(args or ()), **(kwargs or {}))
            except BaseException as error:
                errors.append(error)

        result = original_timer(interval, observe_timer)
        timers.append(result)
        return result

    monkeypatch.setattr(threading, "Timer", timer)
    yield shell, releases, futures, prompts, threads
    for release in releases:
        release.set()
    updator = getattr(shell.prompt_formatter, "updator", None)
    try:
        if updator:
            futures.extend(updator.futures.values())
            if updator.attrs_loaded:
                futures.append(updator.attrs_loaded)
            for prompt in list(updator.prompts.values()):
                prompts.append(prompt)
                futures.extend(prompt.futures)
            for future in futures:
                if not future.cancelled():
                    try:
                        future.result(timeout=10)
                    except BaseException as error:
                        errors.append(error)
    finally:
        for prompt in prompts:
            prompt.stop()
        if updator:
            updator.executor.thread_pool.shutdown(wait=True, cancel_futures=True)
        for timer in timers:
            timer.cancel()
            timer.join(10)
            if timer.is_alive():
                errors.append(AssertionError("timer did not finish"))
        for thread in threads:
            thread.join(10)
            if thread.is_alive():
                errors.append(AssertionError("controller did not finish"))
    if errors:
        raise errors[0]


def _fallback_block(runtime, result="ready", as_field=False):
    shell, releases, _, _, _ = runtime
    entered, release = threading.Event(), threading.Event()
    releases.append(release)

    def callback():
        entered.set()
        if not release.wait(10):
            raise AssertionError("field release timed out")
        return result

    if as_field:

        def update(field, ctx):
            field.value = callback()

        XSH.env["PROMPT_FIELDS"]["slow"] = BasePromptField(updator=update)
    else:
        XSH.env["PROMPT_FIELDS"]["slow"] = callback
    return shell, entered, release


@pytest.mark.parametrize(
    "section,callback,attribute",
    [
        ("PROMPT", "prompt_tokens", "message"),
        ("RIGHT_PROMPT", "rprompt_tokens", "rprompt"),
        ("BOTTOM_TOOLBAR", "bottom_toolbar_tokens", "bottom_toolbar"),
    ],
)
@pytest.mark.parametrize(
    "mapping,template,initial,final,as_field",
    [
        ({"slow": "loading"}, "{slow}", "loading", "ready", False),
        ({"slow": "loading"}, "{slow}", "loading", "ready", True),
        ({}, "{slow}", "{slow}", "ready", False),
        (None, "{slow}", "{slow}", "ready", False),
        ({"other": "wait"}, "{slow}", "{slow}", "ready", False),
        ({"slow": ""}, "{slow}", "", "ready", False),
        ({"slow": "{other}"}, "{slow}|{slow}", "{other}|{other}", "ready|ready", False),
        ({"slow": "é"}, "{slow!r:[{}]}", "['é']", "['ready']", False),
        ({"slow": "é"}, "{slow!a:[{}]}", "['\\xe9']", "['ready']", False),
        ({"slow": "é"}, "{slow!s:[{}]}", "[é]", "[ready]", False),
        (
            {"slow": "{RED}loading{RESET}"},
            "{GREEN}<{slow}>{RESET}",
            "<loading>",
            "<ready>",
            False,
        ),
    ],
)
def test_async_fallback_render_sections(
    _fallback_runtime,
    monkeypatch,
    as_field,
    section,
    callback,
    attribute,
    mapping,
    template,
    initial,
    final,
):
    runtime = _fallback_runtime
    color_case = "{RED}" in (mapping or {}).get("slow", "")
    result = "{BLUE}ready{RESET}" if color_case else "ready"
    shell, entered, release = _fallback_block(runtime, result, as_field)
    if mapping is None:
        del XSH.env["XONSH_ASYNC_PROMPT_FALLBACKS"]
    else:
        XSH.env["XONSH_ASYNC_PROMPT_FALLBACKS"] = mapping
    XSH.env["PROMPT_FIELDS"]["other"] = lambda: pytest.fail(
        "fallback was evaluated recursively"
    )
    XSH.env[section] = template
    rendered = threading.Event()
    original = shell.prompter.app.invalidate

    def observe():
        original()
        value = getattr(shell.prompter, attribute)
        if not callable(value) and _fallback_text(value) == final:
            rendered.set()

    monkeypatch.setattr(shell.prompter.app, "invalidate", observe)
    first = getattr(shell, callback)()
    prompt = shell.prompt_formatter.updator.prompts[attribute]
    runtime[3].append(prompt)
    fields = list(prompt.futures)
    runtime[2].extend(fields)
    assert entered.wait(10)
    assert all(not future.done() for future in fields)
    assert _fallback_text(first) == initial
    if color_case:
        assert ("class:pygments.color.red", "loading") in first
        assert ("class:pygments.color.green", "<") in first
    shell.prompt_formatter.start_update()
    runtime[2].extend(shell.prompt_formatter.updator.futures.values())
    release.set()
    assert rendered.wait(10)
    assert _fallback_text(getattr(shell.prompter, attribute)) == final
    if color_case:
        actual = getattr(shell.prompter, attribute)
        assert ("class:pygments.color.blue", "ready") in actual
        assert ("class:pygments.color.green", "<") in actual
    for future in fields:
        actual_result = future.result(10)
        assert (actual_result.value if as_field else actual_result) == result


@pytest.mark.parametrize("previous", ["old", None, ""])
def test_async_fallback_cached_priority(_fallback_runtime, monkeypatch, previous):
    runtime = _fallback_runtime
    shell, entered, release = _fallback_block(runtime)
    XSH.env["PROMPT"] = "{slow}"
    # Initialize the real formatter/pool, then populate via _run_func.
    shell.prompt_tokens()
    updator = shell.prompt_formatter.updator
    prompt = updator.prompts["message"]
    runtime[3].append(prompt)
    runtime[2].extend(prompt.futures)
    assert entered.wait(10)
    release.set()
    for future in prompt.futures:
        future.result(10)
    expected = updator.executor.thread_pool.submit(
        updator.executor._run_func, lambda: previous, "slow"
    ).result(10)
    assert expected == previous
    XSH.env["PROMPT_FIELDS"].reset()
    shell, entered, release = _fallback_block(runtime)
    XSH.env["XONSH_ASYNC_PROMPT_FALLBACKS"] = {"slow": "must lose"}
    first = shell.prompt_tokens()
    prompt = updator.prompts["message"]
    runtime[3].append(prompt)
    runtime[2].extend(prompt.futures)
    assert entered.wait(10)
    assert prompt.tokens.process() == (
        "" if previous is None else style_as_faded(previous)
    )
    assert _fallback_text(first) == (previous or "")
    rendered = threading.Event()
    original = shell.prompter.app.invalidate

    def observe():
        original()
        value = shell.prompter.message
        if not callable(value) and _fallback_text(value) == "ready":
            rendered.set()

    monkeypatch.setattr(shell.prompter.app, "invalidate", observe)
    shell.prompt_formatter.start_update()
    runtime[2].extend(updator.futures.values())
    release.set()
    assert rendered.wait(10)
    assert _fallback_text(shell.prompter.message) == "ready"


def test_async_fallback_synchronous(_fallback_runtime):
    shell = _fallback_runtime[0]
    XSH.env.update(ENABLE_ASYNC_PROMPT=False, PROMPT="{slow}")
    XSH.env["PROMPT_FIELDS"]["slow"] = lambda: "ready"
    XSH.env["XONSH_ASYNC_PROMPT_FALLBACKS"] = {"slow": "wait"}
    assert _fallback_text(shell.prompt_tokens()) == "ready"
    assert not hasattr(shell.prompt_formatter, "updator")


def test_async_fallback_stop(ptk_shell):
    executor = Executor()
    release, entered = threading.Event(), threading.Event()
    called = threading.Event()
    executor.thread_pool.shutdown()
    executor.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def occupy():
        entered.set()
        assert release.wait(10)

    blocker = executor.thread_pool.submit(occupy)
    prompt = AsyncPrompt("message", ptk_shell[2].prompter, executor)
    try:
        assert entered.wait(10)
        prompt.submit_section(called.set, "slow", 0)
        queued = list(prompt.futures)[0]
        prompt.stop()
        assert queued.cancelled()
        assert not prompt.futures
        assert not called.is_set()
    finally:
        release.set()
        blocker.result(10)
        executor.thread_pool.shutdown(wait=True, cancel_futures=True)


def test_async_fallback_singleline(_fallback_runtime, ptk_shell, monkeypatch):
    runtime = _fallback_runtime
    shell, entered, release = _fallback_block(runtime)
    XSH.env.update(
        PROMPT="{slow}",
        RIGHT_PROMPT="",
        BOTTOM_TOOLBAR="",
        UPDATE_PROMPT_ON_KEYPRESS=False,
    )
    XSH.env["XONSH_ASYNC_PROMPT_FALLBACKS"] = {"slow": "loading"}
    first, rendered, started = threading.Event(), threading.Event(), threading.Event()
    errors = []
    original_invalidate = shell.prompter.app.invalidate
    original_start = PromptUpdator.start
    original_tokens = shell.prompt_tokens
    observed = []

    def tokens():
        value = original_tokens()
        observed.append(value)
        first.set()
        return value

    def invalidate():
        original_invalidate()
        value = shell.prompter.message
        if (
            shell.prompter.app.loop is not None
            and not callable(value)
            and _fallback_text(value) == "ready"
        ):
            rendered.set()

    def start(updator):
        original_start(updator)
        runtime[2].extend(updator.futures.values())
        runtime[2].append(updator.attrs_loaded)
        started.set()

    monkeypatch.setattr(PromptUpdator, "start", start)
    monkeypatch.setattr(shell, "prompt_tokens", tokens)
    monkeypatch.setattr(shell.prompter.app, "invalidate", invalidate)

    def controller():
        try:
            assert first.wait(10)
            assert entered.wait(10)
            assert started.wait(10)
            assert shell.prompter.app.loop is not None
            assert _fallback_text(observed[0]) == "loading"
            assert _fallback_text(shell.prompter.message) == "loading"
            prompt = shell.prompt_formatter.updator.prompts["message"]
            runtime[3].append(prompt)
            runtime[2].extend(prompt.futures)
            assert all(not fut.done() for fut in prompt.futures)
            release.set()
            assert rendered.wait(10)
        except BaseException as error:
            errors.append(error)
        finally:
            release.set()
            ptk_shell[0].send_text("\n")

    thread = threading.Thread(target=controller)
    runtime[4].append(thread)
    thread.start()
    assert shell.singleline() == ""
    thread.join(10)
    assert not thread.is_alive()
    if errors:
        raise errors[0]
    assert rendered.is_set()
    assert _fallback_text(shell.prompter.message) == "ready"


def test_async_fallback_cache_membership_and_lazy_access(ptk_shell):
    executor = Executor()
    release, entered = threading.Event(), threading.Event()
    original_env = XSH.env
    futures = []

    def callback():
        entered.set()
        assert release.wait(10)
        return "ready"

    try:
        # A raw empty cached result is still present. Missing fallback access
        # raises if the cache branch eagerly evaluates it.
        executor.thread_results["slow"] = ""
        XSH.env = {}
        future, intermediate, placeholder = executor.submit(callback, "slow")
        futures.append(future)
        assert entered.wait(10)
        assert intermediate == ""
        assert placeholder == "{slow}"
    finally:
        XSH.env = original_env
        release.set()
        for future in futures:
            future.result(10)
        executor.thread_pool.shutdown(wait=True, cancel_futures=True)


def test_async_fallback_noncallable_fields(_fallback_runtime):
    shell = _fallback_runtime[0]
    XSH.env["PROMPT"] = "{plain}|{unknown}|{$FALLBACK_TEST}"
    XSH.env["FALLBACK_TEST"] = "environment"
    XSH.env["PROMPT_FIELDS"]["plain"] = "literal"
    XSH.env["XONSH_ASYNC_PROMPT_FALLBACKS"] = {
        "plain": "wait",
        "unknown": "wait",
        "$FALLBACK_TEST": "wait",
    }
    assert _fallback_text(shell.prompt_tokens()) == "literal|{unknown}|environment"
    assert not shell.prompt_formatter.updator.prompts["message"].futures
