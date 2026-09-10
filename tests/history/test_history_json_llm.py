"""Concurrency tests for the json history backend.

These cover the access queue that serializes readers and writers of a history
file: nobody may be left behind in it, waiters must always be woken, and the
final flush at shell exit must be bounded so history can never hold up
shutdown.
"""

# pylint: disable=protected-access

import collections
import os
import threading

import pytest

import xonsh.lib.lazyjson as xlj
from xonsh.history.json import JsonHistory, JsonHistoryFlusher, _xhj_queue_turn


@pytest.fixture
def hist(tmpdir, xession, monkeypatch):
    file = tmpdir / "xonsh-HISTORY-TEST-LLM.json"
    h = JsonHistory(filename=str(file), here="yup", sessionid="SESSIONID", gc=False)
    monkeypatch.setattr(xession, "history", h)
    xession.env["HISTCONTROL"] = set()
    yield h


def wait_for(predicate, timeout=5.0):
    """Spin until ``predicate`` holds, returning whether it did."""
    deadline = threading.TIMEOUT_MAX if timeout is None else timeout
    step = 0.005
    waited = 0.0
    while waited < deadline:
        if predicate():
            return True
        threading.Event().wait(step)
        waited += step
    return predicate()


def run_in_thread(func):
    """Start ``func`` on a daemon thread and return a done-event for it."""
    done = threading.Event()

    def target():
        try:
            func()
        finally:
            done.set()

    threading.Thread(target=target, daemon=True).start()
    return done


#
# _xhj_queue_turn
#


def test_queue_turn_hands_out_turns_in_order():
    queue = collections.deque()
    cond = threading.Condition()
    order = []
    release = threading.Event()
    items = ["a", "b", "c"]
    for item in items:
        queue.append(item)

    def take(item):
        with _xhj_queue_turn(queue, item, cond) as my_turn:
            assert my_turn
            order.append(item)
            release.wait(5.0)

    events = [run_in_thread(lambda item=item: take(item)) for item in items]
    assert wait_for(lambda: order == ["a"])
    release.set()
    for done in events:
        assert done.wait(5.0)
    assert order == items
    assert not queue


def test_queue_turn_releases_the_slot_when_the_body_raises():
    """An item left in the queue would wedge every later reader and writer."""
    queue = collections.deque()
    cond = threading.Condition()
    queue.append("boom")

    with pytest.raises(ZeroDivisionError):
        with _xhj_queue_turn(queue, "boom", cond):
            raise ZeroDivisionError("the body blew up")

    assert not queue

    # the queue is still usable afterwards
    queue.append("next")
    with _xhj_queue_turn(queue, "next", cond) as my_turn:
        assert my_turn
    assert not queue


def test_queue_turn_wakes_the_next_waiter():
    """The turn holder must notify on the way out, not only on timeout."""
    queue = collections.deque()
    cond = threading.Condition()
    queue.append("first")
    queue.append("second")
    reached = threading.Event()

    def second():
        with _xhj_queue_turn(queue, "second", cond) as my_turn:
            assert my_turn
            reached.set()

    done = run_in_thread(second)
    assert not reached.wait(0.1)
    with _xhj_queue_turn(queue, "first", cond):
        pass
    assert done.wait(5.0)
    assert reached.is_set()
    assert not queue


def test_queue_turn_gives_up_after_the_timeout():
    queue = collections.deque()
    cond = threading.Condition()
    stuck = object()
    queue.append(stuck)
    queue.append("me")

    with _xhj_queue_turn(queue, "me", cond, timeout=0.05) as my_turn:
        assert my_turn is False

    assert list(queue) == [stuck]


#
# JsonHistoryFlusher
#


def test_flusher_threads_are_daemon(hist, xession):
    """Non-daemon flushers are joined before the at-exit flush even runs."""
    hist.append({"inp": "still alive", "rtn": 0})
    hf = hist.flush()
    assert hf.daemon
    hf.join(5.0)
    assert not hf.is_alive()


def test_exit_flush_gives_up_on_a_wedged_writer(hist, xession, capsys):
    """A writer stuck inside dump() must not block shutdown."""
    xession.env["XONSH_HISTORY_EXIT_FLUSH_TIMEOUT"] = 0.05
    wedged = threading.Event()
    release = threading.Event()

    class WedgedFlusher(JsonHistoryFlusher):
        def dump(self):
            wedged.set()
            release.wait(10.0)

    WedgedFlusher(hist.filename, (), hist._queue, hist._cond, skip=None)
    assert wedged.wait(5.0)

    hist.append({"inp": "lost to the timeout", "rtn": 0})
    done = run_in_thread(lambda: hist.flush(at_exit=True))
    assert done.wait(5.0), "the exit flush blocked on a wedged writer"

    err = capsys.readouterr().err
    assert "dropping 1 command(s)" in err
    assert "XONSH_HISTORY_EXIT_FLUSH_TIMEOUT" in err

    release.set()


def test_exit_flush_gives_up_on_a_stalled_queue_entry(hist, xession):
    xession.env["XONSH_HISTORY_EXIT_FLUSH_TIMEOUT"] = 0.05
    stalled = object()
    hist._queue.append(stalled)
    hist.append({"inp": "lost to the timeout", "rtn": 0})

    done = run_in_thread(lambda: hist.flush(at_exit=True))
    assert done.wait(5.0), "the exit flush blocked on a stalled queue entry"
    assert list(hist._queue) == [stalled], "the exit flush stayed in the queue"


def test_exit_flush_still_writes_when_the_queue_is_free(hist, xession):
    hist.append({"inp": "kept", "rtn": 0})
    hist.flush(at_exit=True)
    with xlj.LazyJSON(hist.filename) as lj:
        assert [cmd["inp"] for cmd in lj["cmds"].load()] == ["kept"]
        assert lj["locked"] is False
    assert not hist._queue


def test_dump_removes_the_temp_file_when_the_write_fails(
    hist, xession, monkeypatch, capsys
):
    def boom(*args, **kwargs):
        raise OSError("no space left on device")

    monkeypatch.setattr(xlj, "ljdump", boom)
    hist.append({"inp": "doomed", "rtn": 0})
    hist.flush(at_exit=True)

    assert "failed to write" in capsys.readouterr().err
    dirname = os.path.dirname(hist.filename)
    leftovers = [f for f in os.listdir(dirname) if f.endswith(".json.tmp")]
    assert leftovers == []


#
# JsonCommandField
#


def flush_and_wait(hist):
    hf = hist.flush()
    if hf is not None:
        hf.join(5.0)
    assert wait_for(lambda: not hist._queue)


def test_command_field_read_wakes_waiters(hist, xession):
    """Reading a field pops the queue; it must notify or waiters park forever."""
    hist.append({"inp": "one", "rtn": 0})
    hist.append({"inp": "two", "rtn": 0})
    flush_and_wait(hist)

    blocker = object()
    hist._queue.append(blocker)

    read = []
    reader_done = run_in_thread(lambda: read.append(hist.inps[0]))
    assert wait_for(lambda: len(hist._queue) == 2)

    waiter = object()
    hist._queue.append(waiter)
    waiter_reached = threading.Event()

    def behind_the_reader():
        with _xhj_queue_turn(hist._queue, waiter, hist._cond):
            waiter_reached.set()

    waiter_done = run_in_thread(behind_the_reader)
    assert wait_for(lambda: len(hist._queue) == 3)

    with hist._cond:
        hist._queue.remove(blocker)
        hist._cond.notify_all()

    assert reader_done.wait(5.0)
    assert read == ["one"]
    assert waiter_done.wait(5.0), "the field read did not wake the next waiter"
    assert waiter_reached.is_set()
    assert not hist._queue


def test_command_field_read_error_does_not_wedge_the_queue(hist, xession):
    hist.append({"inp": "one", "rtn": 0})
    flush_and_wait(hist)
    os.remove(hist.filename)

    with pytest.raises(OSError):
        _ = hist.inps[0]

    assert not hist._queue, "the failed read stayed at the head of the queue"
