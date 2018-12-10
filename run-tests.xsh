#!/usr/bin/env xonsh
$RAISE_SUBPROC_ERROR = True

run_separately = [
    'tests/test_ptk_highlight.py',
    ]

![pytest  @($ARGS[1:]) --ignore @(run_separately)]
for fname in run_separately:
    ![pytest  @($ARGS[1:]) @(fname)]
