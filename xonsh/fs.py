"""
Backported functions to implement the PEP 519 (Adding a file system path protocol) API.
"""

from os import PathLike, fspath, fsencode, fsdecode  # noqa
