from livereload import Server, shell
from pathlib import Path
import sys

cur_dir = Path(__file__).parent
server = Server()

if "no" not in sys.argv:
    exts = ("rst", "py", "jinja2")
    print(f"Watching file changes {exts}")
    cmd = shell("make html", cwd=str(cur_dir))
    for ext in exts:
        # nested or
        server.watch(str(cur_dir / f"**.{ext}"), cmd)
        # top level
        server.watch(str(cur_dir / f"**/*.{ext}"), cmd)

server.serve(root=str(cur_dir / "_build" / "html"))
