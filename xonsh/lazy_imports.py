"""Lazy import utilities for xonsh performance optimization.

This module provides utilities to defer expensive imports until they are actually needed,
significantly improving shell startup performance.
"""

import importlib
from typing import Any


class LazyModule:
    """A lazy-loading module wrapper that defers import until first access."""

    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module = None
        self._import_attempted = False

    def _ensure_imported(self):
        """Ensure the module is imported, importing it if necessary."""
        if not self._import_attempted:
            try:
                self._module = importlib.import_module(self._module_name)
            except ImportError as e:
                # Store the error to re-raise it on access
                self._import_error = e
                self._module = None
            finally:
                self._import_attempted = True

        if self._module is None and hasattr(self, "_import_error"):
            raise self._import_error

        return self._module

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the lazy-loaded module."""
        module = self._ensure_imported()
        return getattr(module, name)

    def __call__(self, *args, **kwargs):
        """Make the lazy module callable if the wrapped module is callable."""
        module = self._ensure_imported()
        return module(*args, **kwargs)

    def __repr__(self) -> str:
        if self._module is not None:
            return f"<LazyModule {self._module_name!r} (loaded)>"
        return f"<LazyModule {self._module_name!r} (not loaded)>"


class LazyObject:
    """A lazy-loading object wrapper for specific attributes within modules."""

    def __init__(self, module_name: str, attr_name: str):
        self._module_name = module_name
        self._attr_name = attr_name
        self._obj = None
        self._import_attempted = False

    def _ensure_imported(self):
        """Ensure the object is imported, importing it if necessary."""
        if not self._import_attempted:
            try:
                module = importlib.import_module(self._module_name)
                self._obj = getattr(module, self._attr_name)
            except (ImportError, AttributeError) as e:
                self._import_error = e
                self._obj = None
            finally:
                self._import_attempted = True

        if self._obj is None and hasattr(self, "_import_error"):
            raise self._import_error

        return self._obj

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the lazy-loaded object."""
        obj = self._ensure_imported()
        return getattr(obj, name)

    def __call__(self, *args, **kwargs):
        """Make the lazy object callable if the wrapped object is callable."""
        obj = self._ensure_imported()
        return obj(*args, **kwargs)

    def __repr__(self) -> str:
        if self._obj is not None:
            return f"<LazyObject {self._module_name}.{self._attr_name} (loaded)>"
        return f"<LazyObject {self._module_name}.{self._attr_name} (not loaded)>"


def lazy_import_module(module_name: str) -> LazyModule:
    """Create a lazy-loading wrapper for a module.

    Args:
        module_name: The fully qualified name of the module to lazy-load

    Returns:
        A LazyModule that will import the actual module on first access

    Example:
        >>> # Instead of: import xonsh.completers.bash_completion
        >>> bash_completion = lazy_import_module('xonsh.completers.bash_completion')
        >>> # Module is only imported when bash_completion is actually used
        >>> completer = bash_completion.BashCompleter()  # Import happens here
    """
    return LazyModule(module_name)


def lazy_import_object(module_name: str, attr_name: str) -> LazyObject:
    """Create a lazy-loading wrapper for a specific object within a module.

    Args:
        module_name: The fully qualified name of the module
        attr_name: The name of the attribute/object within the module

    Returns:
        A LazyObject that will import the module and extract the object on first access

    Example:
        >>> # Instead of: from xonsh.history.main import History
        >>> History = lazy_import_object('xonsh.history.main', 'History')
        >>> # Module is only imported when History is actually used
        >>> hist = History()  # Import happens here
    """
    return LazyObject(module_name, attr_name)


# Convenience function for backward compatibility
def lazy_import(
    module_name: str, attr_name: str | None = None
) -> LazyModule | LazyObject:
    """Create a lazy import for a module or object.

    This is a convenience function that chooses between lazy_import_module
    and lazy_import_object based on whether attr_name is provided.

    Args:
        module_name: The fully qualified name of the module
        attr_name: Optional attribute name within the module

    Returns:
        LazyModule if attr_name is None, LazyObject otherwise
    """
    if attr_name is None:
        return lazy_import_module(module_name)
    else:
        return lazy_import_object(module_name, attr_name)
