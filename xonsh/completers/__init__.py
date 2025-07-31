"""Completers for xonsh."""

from xonsh.lazy_imports import lazy_import_object

bash_complete_line = lazy_import_object(
    "xonsh.completers.bash_completion", "bash_complete_line"
)
python_signature_complete = lazy_import_object(
    "xonsh.completers.python", "python_signature_complete"
)
complete_path = lazy_import_object("xonsh.completers.path", "complete_path")

__all__ = [
    "bash_complete_line",
    "python_signature_complete",
    "complete_path",
]
