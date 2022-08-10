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
