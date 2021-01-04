from livereload import Server, shell
from pathlib import Path
import sys

cur_dir = Path(__file__).parent
server = Server()

if "no" not in sys.argv:
    for ext in ("rst", "py", "jinja2"):
        server.watch(
            str(cur_dir / f"*.{ext}"),
            shell("make html", cwd=str(cur_dir)),
        )

server.serve(root=str(cur_dir / "_build" / "html"))
