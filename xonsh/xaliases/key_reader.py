# inspired from https://fishshell.com/docs/current/cmds/fish_key_reader.html#cmd-fish-key-reader

import asyncio

from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys

from xonsh.cli_utils import ArgParserAlias


async def _key_reader(continous=False) -> None:
    """the code is from ptk's recipe
    https://python-prompt-toolkit.readthedocs.io/en/master/pages/asking_for_input.html#reading-keys-from-stdin-one-key-at-a-time-but-without-a-prompt
    """
    done = asyncio.Event()
    input = create_input()

    def keys_ready():
        for key_press in input.read_keys():
            print(key_press)

            if key_press.key == Keys.ControlC or (not continous):
                done.set()

    with input.raw_mode():
        with input.attach(keys_ready):
            await done.wait()


def key_reader(continous=False):
    """
        Study input received from the terminal and can help with key binds.
        The program is interactive and works on standard input.
        Individual characters themselves and their hexadecimal values are displayed.

    Parameters
    ----------
    continous : -c, --continous
        begins a session where multiple key sequences can be inspected.
        By default the program exits after capturing a single key sequence
    """
    if continous:
        print("Press Ctrl+C to exit")
    asyncio.run(_key_reader(continous))


xonsh_alias = ArgParserAlias(func=key_reader, has_args=True, prog="xexec")

if __name__ == "__main__":
    key_reader(True)
