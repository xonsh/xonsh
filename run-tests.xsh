#!/usr/bin/env xonsh
import sys
args = sys.argv[1:]


def replace_args(num):
    """
    Replace %d to num for avoid overwrite files

    Example of args: --junitxml=junit/test-results.%d.xml
    """
    return [
        (arg % num) if "%d" in arg else arg
        for arg in args]

$RAISE_SUBPROC_ERROR = True

run_separately = [
    'tests/test_main.py',
    'tests/test_ptk_highlight.py',
    ]
ignores = []
for fname in run_separately:
    ignores.append('--ignore')
    ignores.append(fname)
![pytest @(replace_args(0)) @(ignores)]
for index, fname in enumerate(run_separately):
    ![pytest @(replace_args(index+1)) @(fname)]

echo "---------- Running flake8 ----------"
python -m flake8
    
