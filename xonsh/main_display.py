"""The main xonsh displaye."""
import urwid

from xonsh.shell_view import ShellView

class MainDisplay(object):

    def __init__(self):
        self.shell = shell = ShellView()
        self.view = urwid.LineBox(
            urwid.Pile([
                ('weight', 70, shell),
                ('fixed', 1, urwid.Filler(urwid.Edit('focus test edit: '))),
            ]),
            )
        urwid.connect_signal(shell, 'title', self.set_title)
        urwid.connect_signal(shell, 'closed', self.quit)


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
        self.loop = self.shell.main_loop = loop
        while True:
            try:
                self.loop.run()
            except KeyboardInterrupt:
                self.reset_status(status="YOLO!   ")
            else:
                break
