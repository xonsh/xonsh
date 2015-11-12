#!/bin/sh
#
# Run all the nosetests or just the ones relevant for the edited files.
#
if [[ $1 == "-e" ]]; then
    tmp_file=$(mktemp /tmp/nose_tests_XXXXXX)
    git status -s |
        awk '/\.py$/ { print $2 }' |
        while read f; do
            if [[ $f == xonsh/* ]]; then
                f="tests/test_$(basename  $f)"
                if [[ -f $f ]]; then
                    echo $f
                fi
            else
                echo $f
            fi
        done |
        sort -u > $tmp_file
    XONSHRC=/dev/null nosetests -v $(< $tmp_file)
    rm $tmp_file
else
    XONSHRC=/dev/null nosetests
fi
