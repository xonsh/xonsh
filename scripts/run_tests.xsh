#!/usr/bin/env xonsh --no-rc
#
# Run all the nosetests or just the ones relevant for the edited files in the
# current uncommited git change or just the ones named on the command line.
# Your cwd must be the top of the project tree.
#
# Usage:
#   run_tests.xsh [edited | all | list of test names]
#
# You can omit the "all" argument if you want all tests run.
#
import os.path
import sys

if not os.path.isdir('.git'):
    print('No .git directory. The cwd must be the top of the project tree.',
          file=sys.stderr)
    sys.exit(1)

if len($ARGS) == 1:
    # Run all tests.
    $[make build-tables] # ensure lexer/parser table module is up to date
    $[env XONSHRC='' nosetests]
elif len($ARGS) == 2 and $ARG1 == 'all':
    # Run all tests.
    $[make build-tables] # ensure lexer/parser table module is up to date
    $[env XONSHRC='' nosetests]
elif len($ARGS) == 2 and $ARG1 == 'edited':
    # Run just the tests for the files edited in the uncommited change.
    tests = set()
    for edited_fname in $(git status -s).split():
        if not edited_fname.endswith('.py'):
            continue
        if edited_fname.startswith('xonsh/'):
            test_fname = 'tests/test_' + edited_fname[len('xonsh/')]
            if os.path.exists(test_fname):
                tests.add(test_fname)
        elif edited_fname.startswith('tests/'):
            tests.add(edited_fname)
        else:
            print('Ignoring file because I cannot find a test for: {!r}.'.
                  format(edited_fname), file=sys.stderr)

    if tests:
        $[make build-tables] # ensure lexer/parser table module is up to date
        $[env XONSHRC='' nosetests -v @(sorted(tests))]
    else:
        print('Cannot find any tests in the pending changes.', file=sys.stderr)
else:
    # Run the named tests.
    tests = set()
    for test_fname in $ARGS[1:]:
        if not test_fname.startswith('tests/'):
            if not test_fname.startswith('test_'):
                test_fname = 'tests/test_' + test_fname
            if not test_fname.endswith('.py'):
                test_fname += '.py'
        if os.path.exists(test_fname):
            tests.add(test_fname)
        else:
            print('Cannot find test module {!r}; ignoring the argument.'.
                  format(test_fname), file=sys.stderr)

    if tests:
        $[make build-tables] # ensure lexer/parser table module is up to date
        $[env XONSHRC='' nosetests -v @(sorted(tests))]
    else:
        print('Cannot find any tests matching {}.'.format($ARGS[1:]),
              file=sys.stderr)
        sys.exit(1)
