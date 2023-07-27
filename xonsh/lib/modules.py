import contextlib
import functools
import importlib
import importlib.util as im_util
import os
from collections import OrderedDict


class ModuleFinder:
    """Reusable module matcher. Can be used by other completers like Python to find matching script completions"""

    extensions = (".py", ".xsh")

    def __init__(self, *names: "str"):
        """Helper class to search and load Python modules

        Parameters
        ----------
        names
            extra search paths/package-names to use if finding module on namespace package fails.
            paths should have a path literal to indicate it is a path. Otherwise it is treated as a package name.
        """

        self.contextual = True

        # unique but maintain order
        self._pkgs: dict[str, None] = OrderedDict()
        self._paths: dict[str, None] = OrderedDict()
        for pk in names:
            if os.sep in pk:
                self._paths[pk] = None
            else:
                self._pkgs[pk] = None

        self._file_names_cache: dict[str, str] = {}
        self._path_st_mtimes: dict[str, float] = {}

    def _get_new_paths(self):
        for path in self._paths:
            if not os.path.isdir(path):
                continue
            # check if path is updated
            old_mtime = self._path_st_mtimes.get(path, 0)
            new_mtime = os.stat(path).st_mtime
            if old_mtime >= new_mtime:
                continue
            self._path_st_mtimes[path] = os.stat(path).st_mtime
            yield path

    def _find_file_path(self, name):
        # `importlib.machinery.FileFinder` wasn't useful as the findspec handles '.' differently
        if name in self._file_names_cache:
            return self._file_names_cache[name]

        found = None
        entries = {}
        for path in self._get_new_paths():
            from xonsh.environ import scan_dir_for_source_files

            for file, entry in scan_dir_for_source_files(path):
                file_name = os.path.splitext(entry.name)[0]
                if file_name not in entries:
                    # do not override. prefer the first one that appears on the path list
                    entries[file_name] = file
                if file_name == name:
                    found = file
            if found:
                # search a directory completely since we cache path-mtime
                break
        self._file_names_cache.update(entries)
        return found

    @staticmethod
    def import_module(path, name: str):
        """given the file location import as module"""
        pkg = path.replace(os.sep, ".")
        spec = im_util.spec_from_file_location(f"{pkg}.{name}", path)
        if not spec:
            return
        module = im_util.module_from_spec(spec)
        if not spec.loader:
            return
        spec.loader.exec_module(module)  # type: ignore
        return module

    @functools.lru_cache(maxsize=None)  # noqa
    def get_module(self, module: str):
        for name in [
            module,
            f"_{module}",  # naming convention to not clash with actual python package
        ]:
            for base in self._pkgs:
                with contextlib.suppress(ModuleNotFoundError):
                    return importlib.import_module(f"{base}.{name}")
        file = self._find_file_path(module)
        if file:
            return self.import_module(file, module)
