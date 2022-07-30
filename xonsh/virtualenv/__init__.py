from pathlib import Path

from virtualenv.activation.via_template import ViaTemplateActivator  # type: ignore


class XonshActivator(ViaTemplateActivator):
    def templates(self):
        yield Path("activate.xsh")

    @classmethod
    def supports(cls, interpreter):
        return interpreter.version_info >= (3, 5)
