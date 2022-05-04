from livereload import Server, shell
from pathlib import Path
import sys

doc_dir = Path(__file__).parent
root_dir = doc_dir.parent
server = Server()


def get_paths(*exts):
    for tp in exts:
        # top level
        yield root_dir / f"**.{tp}"
        # nested
        yield root_dir / f"**/*.{tp}"


if "no" not in sys.argv:
    exts = ("rst", "py", "jinja2", "md")
    cmd = shell("make html", cwd=str(doc_dir))
    for path in get_paths(*exts):
        print(f"watching {path}")
        server.watch(str(path), cmd)

server.serve(root=str(doc_dir / "_build" / "html"))
