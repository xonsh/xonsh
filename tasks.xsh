#!/usr/bin/env xonsh

"""Run as `xonsh tasks.xsh`"""

from arger import Arger

arg = Arger(description="List of tasks useful during development much like Makefile.")


@arg.add_cmd
def vendor():
    """Vendorize packages listed in xonsh/vendored/deps.txt"""

    print("Vendor PTK")
    pushd xonsh/vended_ptk

    # use --upgrade to force install
    pip install --upgrade -r deps.txt -t .
    cp prompt_toolkit-*.dist-info/LICENSE LICENSE-prompt-toolkit
    cp wcwidth-*.dist-info/LICENSE LICENSE-wcwidth
    rm -rd *.dist-info
    popd


if __name__ == '__main__':
    arg.run()
