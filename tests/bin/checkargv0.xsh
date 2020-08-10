#!/usr/bin/env xonsh
res = True
script = """import os
path = "/proc/{}/cmdline".format(os.getpid())
with open(path, "r") as f:
    lines = f.read().split("\x00")
    print(lines[0])"""

def check(python):
    argv0 = $(@(python) -c @(script)).rstrip()

    if argv0 == python:
        return True

    print("Unexpected argv[0]: {} != {}".format(argv0, python))
    return False


python = "python"
res &= check(python)

python = $(which -s python)
res &= check(python)
if res:
    print("OK")
