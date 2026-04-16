import threading


def test_current_job(xession):
    prompts = xession.env["PROMPT_FIELDS"]
    cmds = (["echo", "hello"], "|", ["grep", "h"])

    prompts.reset()
    assert format(prompts.pick("current_job")) == ""

    with prompts["current_job"].update_current_cmds(cmds):
        prompts.reset()
        assert format(prompts.pick("current_job")) == "grep"

    prompts.reset()
    assert format(prompts.pick("current_job")) == ""


def test_current_job_thread_safe(xession):
    """Background thread commands must not leak into the main thread's prompt.
    Regression test for xonsh/xonsh#3175.
    """
    field = xession.env["PROMPT_FIELDS"]["current_job"]
    main_cmds = (["fg_cmd"],)
    bg_cmds = (["bg_cmd"],)
    barrier = threading.Barrier(2, timeout=5)
    bg_value = None

    def background():
        nonlocal bg_value
        with field.update_current_cmds(bg_cmds):
            # signal main thread to check while we hold bg_cmds
            barrier.wait()
            # wait for main thread to finish checking
            barrier.wait()
            # verify background thread sees its own command
            field.update(None)
            bg_value = field.value

    t = threading.Thread(target=background)
    t.start()

    # wait until background thread has set bg_cmds
    barrier.wait()

    # main thread should not see bg_cmds
    field.update(None)
    assert field.value is None

    # even with main thread's own cmds, bg should not interfere
    with field.update_current_cmds(main_cmds):
        field.update(None)
        assert field.value == "fg_cmd"

    # release background thread
    barrier.wait()
    t.join()

    # background thread saw its own command
    assert bg_value == "bg_cmd"
