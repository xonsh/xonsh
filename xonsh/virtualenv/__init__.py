from virtualenv.activation.via_template import ViaTemplateActivator  # type: ignore
from virtualenv.util.path import Path  # type: ignore


class XonshActivator(ViaTemplateActivator):
    def templates(self):
        yield Path("activate.xsh")

    @classmethod
    def supports(cls, interpreter):
        return interpreter.version_info >= (3, 5)
