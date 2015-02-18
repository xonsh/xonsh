"""The main xonsh display."""
import urwid
from urwid.vterm import Terminal

from xonsh.shell import Shell
#from xonsh.shell_view import ShellView

class MainDisplay(object):

    def __init__(self):
        self.shell = shell = Shell()
        self.shellview = shellview = Terminal(shell.cmdloop)
        self.view = urwid.LineBox(
            urwid.Pile([
                ('weight', 70, shellview),
                ('fixed', 1, urwid.Filler(urwid.Edit('focus test edit: '))),
            ]),
            )
        urwid.connect_signal(shellview, 'title', self.set_title)
        urwid.connect_signal(shellview, 'closed', self.quit)


    def set_title(self, widget, title):
        self.view.set_title(title)

    def quit(self, *args, **kwargs):
        raise urwid.ExitMainLoop()

    def handle_key(self, key):
        if key in ('q', 'Q'):
            self.quit()

    def main(self, line=1, col=1):
        loop = urwid.MainLoop(self.view,
            handle_mouse=False,
            unhandled_input=self.handle_key)
        loop.screen.set_terminal_properties(256)
        self.loop = self.shellview.main_loop = loop
        while True:
            try:
                self.loop.run()
            except KeyboardInterrupt:
                self.reset_status(status="YOLO!   ")
            else:
                break
