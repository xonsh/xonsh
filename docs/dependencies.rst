Dependencies
============
Xonsh currently has the following external dependencies,

*Run Time:*

    #. Python v3.4+
    #. PLY (optional, included with xonsh)

Pip supports "extra" dependendcies in the form of ``xonsh[ptk,linux]``, where the list in the brackets identify the optional featues

Xonsh currently has the following extras

    #. ``ptk``: prompt-toolkit, `pygments`:
       *advanced readline library, syntax-highlighting, line-editing*
    #. ``proctitle``: setproctitle: *change the title of terminal to reflect the current subprocess*
    #. ``linux``: distro: *linux specific platform information*
    #. ``mac``: gnureadline: *GNU's featureful version of readline*
    #. ``win``: win_unicode_console: *enables the use of Unicode in windows consoles*

In addition, xonsh integrates with Jupyter, an in-browser REPL, enabling the use of xonsh in jupyter notebooks

Development Dependencies
========================

If you want to develop xonsh, it is extremely recommended to install the depdencies listed in `requirements-docs.txt <https://github.com/xonsh/xonsh/blob/master/requirements-docs.txt>`_ (to generate documentation) and `requirements-tests.txt <https://github.com/xonsh/xonsh/blob/master/requirements-tests.txt>`_ (to run the test suite).
