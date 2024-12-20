from virtualenv.activation.via_template import ViaTemplateActivator  # type: ignore


class XonshActivator(ViaTemplateActivator):
    def templates(self):
        yield "activate.xsh"

    @staticmethod
    def quote(string):
        # leave string unchanged since we do quoting in activate.xsh (see #5699)
        return string

    @classmethod
    def supports(cls, interpreter):
        return interpreter.version_info >= (3, 5)
