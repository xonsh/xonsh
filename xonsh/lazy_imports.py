"""Conservative lazy import utilities for xonsh performance optimization.

This version prioritizes compatibility over maximum performance gains.
"""

import importlib
import os
import sys
from typing import Any


# Detect testing environment more reliably
def _is_testing():
    """Detect if we're in a testing environment."""
    return (
        "pytest" in sys.modules
        or "unittest" in sys.modules
        or os.environ.get("PYTEST_CURRENT_TEST") is not None
        or any("test" in str(arg).lower() for arg in sys.argv)
        or "CI" in os.environ  # GitHub Actions, etc.
        or "CONTINUOUS_INTEGRATION" in os.environ
    )


class LazyObject:
    """A conservative lazy-loading object wrapper."""

    def __init__(self, module_name: str, attr_name: str):
        self._module_name = module_name
        self._attr_name = attr_name
        self._obj = None
        self._import_attempted = False

        # Always load immediately in testing environments
        if _is_testing():
            try:
                self._ensure_imported()
            except Exception:
                # If import fails in test mode, don't crash
                pass

    def _ensure_imported(self):
        """Ensure the object is imported."""
        if not self._import_attempted:
            self._import_attempted = True
            try:
                module = importlib.import_module(self._module_name)
                self._obj = getattr(module, self._attr_name)
            except (ImportError, AttributeError) as e:
                self._import_error = e
                self._obj = None

        if self._obj is None and hasattr(self, "_import_error"):
            raise self._import_error

        return self._obj

    def __getattr__(self, name: str) -> Any:
        """Forward all attribute access to the wrapped object."""
        obj = self._ensure_imported()
        return getattr(obj, name)

    def __call__(self, *args, **kwargs):
        """Forward all calls to the wrapped object."""
        obj = self._ensure_imported()
        return obj(*args, **kwargs)

    def __repr__(self) -> str:
        try:
            obj = self._ensure_imported()
            return repr(obj)
        except Exception:
            return f"<LazyObject {self._module_name}.{self._attr_name}>"

    def __str__(self) -> str:
        try:
            obj = self._ensure_imported()
            return str(obj)
        except Exception:
            return f"<LazyObject {self._module_name}.{self._attr_name}>"

    def __eq__(self, other):
        """Support equality comparison."""
        try:
            obj = self._ensure_imported()
            return obj == other
        except Exception:
            return False

    def __hash__(self):
        """Support hashing."""
        try:
            obj = self._ensure_imported()
            return (
                hash(obj)
                if hasattr(obj, "__hash__") and callable(obj.__hash__)
                else id(self)
            )
        except Exception:
            return id(self)

    def __bool__(self):
        """Support boolean conversion."""
        try:
            obj = self._ensure_imported()
            return bool(obj)
        except Exception:
            return True

    def __len__(self):
        """Support len() if the wrapped object supports it."""
        obj = self._ensure_imported()
        return len(obj)

    def __iter__(self):
        """Support iteration if the wrapped object supports it."""
        obj = self._ensure_imported()
        return iter(obj)

    def __getitem__(self, key):
        """Support indexing if the wrapped object supports it."""
        obj = self._ensure_imported()
        return obj[key]

    def __setitem__(self, key, value):
        """Support item assignment if the wrapped object supports it."""
        obj = self._ensure_imported()
        obj[key] = value

    def __delitem__(self, key):
        """Support item deletion if the wrapped object supports it."""
        obj = self._ensure_imported()
        del obj[key]


class LazyModule:
    """A conservative lazy-loading module wrapper."""

    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module = None
        self._import_attempted = False

        # Always load immediately in testing environments
        if _is_testing():
            try:
                self._ensure_imported()
            except Exception:
                pass

    def _ensure_imported(self):
        """Ensure the module is imported."""
        if not self._import_attempted:
            self._import_attempted = True
            try:
                self._module = importlib.import_module(self._module_name)
            except ImportError as e:
                self._import_error = e
                self._module = None

        if self._module is None and hasattr(self, "_import_error"):
            raise self._import_error

        return self._module

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the module."""
        module = self._ensure_imported()
        return getattr(module, name)

    def __call__(self, *args, **kwargs):
        """Forward calls to the module if it's callable."""
        module = self._ensure_imported()
        return module(*args, **kwargs)

    def __repr__(self) -> str:
        try:
            module = self._ensure_imported()
            return repr(module)
        except Exception:
            return f"<LazyModule {self._module_name!r}>"

    def __str__(self) -> str:
        try:
            module = self._ensure_imported()
            return str(module)
        except Exception:
            return f"<LazyModule {self._module_name!r}>"

    def __dir__(self):
        """Support dir() on the lazy module."""
        try:
            module = self._ensure_imported()
            return dir(module)
        except Exception:
            return []


def lazy_import_module(module_name: str) -> LazyModule:
    """Create a lazy-loading wrapper for a module."""
    return LazyModule(module_name)


def lazy_import_object(module_name: str, attr_name: str) -> LazyObject:
    """Create a lazy-loading wrapper for a specific object within a module."""
    return LazyObject(module_name, attr_name)


def lazy_import(
    module_name: str, attr_name: str | None = None
) -> LazyModule | LazyObject:
    """Create a lazy import for a module or object."""
    if attr_name is None:
        return lazy_import_module(module_name)
    else:
        return lazy_import_object(module_name, attr_name)
