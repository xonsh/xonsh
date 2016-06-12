"""
A helper xonsh enterpoint for developers.

With this file, we can run/test xonsh inside the xonsh's repo like following:

$ python3 main.py -c 'echo hi'
"""

from xonsh.main import main


if __name__ == '__main__':
    main()
