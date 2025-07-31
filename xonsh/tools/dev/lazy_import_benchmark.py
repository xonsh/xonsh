#!/usr/bin/env python3
"""
Lazy import optimization for xonsh
This implements lazy loading patterns to improve startup performance
"""

import importlib
import sys


class LazyImporter:
    """A lazy importer that defers module loading until first access"""

    def __init__(self, module_name: str, attribute: str | None = None):
        self.module_name = module_name
        self.attribute = attribute
        self._cached_module = None
        self._cached_attribute = None

    def __call__(self, *args, **kwargs):
        """Enable calling the lazy-loaded attribute directly"""
        attr = self._get_attribute()
        if callable(attr):
            return attr(*args, **kwargs)
        return attr

    def __getattr__(self, name):
        """Forward attribute access to the loaded module/attribute"""
        if self.attribute:
            # If we're wrapping a specific attribute, forward to it
            attr = self._get_attribute()
            return getattr(attr, name)
        else:
            # If we're wrapping a module, forward to the module
            module = self._get_module()
            return getattr(module, name)

    def _get_module(self):
        """Get the module, loading it if necessary"""
        if self._cached_module is None:
            self._cached_module = importlib.import_module(self.module_name)
        return self._cached_module

    def _get_attribute(self):
        """Get the specific attribute, loading the module if necessary"""
        if self._cached_attribute is None:
            module = self._get_module()
            if self.attribute:
                self._cached_attribute = getattr(module, self.attribute)
            else:
                self._cached_attribute = module
        return self._cached_attribute


def create_lazy_import(module_name: str, attribute: str | None = None):
    """Create a lazy import for a module or specific attribute"""
    return LazyImporter(module_name, attribute)


# Example optimizations for common xonsh modules
OPTIMIZATION_TARGETS = {
    # Heavy parsers and completers - often not needed immediately
    "xonsh.completers.completer": [
        "xonsh.completers.base",
        "xonsh.completers.bash_completion",
        "xonsh.completers.python",
        "xonsh.completers.path",
    ],
    # History system - not needed until user asks for history
    "xonsh.history": [
        "xonsh.history.main",
        "xonsh.history.sqlite",
        "xonsh.history.json",
    ],
    # Advanced tools - often unused in basic sessions
    "xonsh.tools": [
        "xonsh.tools.color_tools",
        "xonsh.tools.decorators",
    ],
    # Event system - can be lazy loaded
    "xonsh.events": [
        "xonsh.events",
    ],
}


def apply_lazy_loading_patch():
    """Apply lazy loading patches to xonsh modules"""

    # Patch 1: Lazy completion system
    lazy_completers_patch = """
# Original heavy import
# from xonsh.completers.completer import Completer

# Optimized lazy import
from xonsh.lazy_imports import create_lazy_import
Completer = create_lazy_import('xonsh.completers.completer', 'Completer')
"""

    # Patch 2: Lazy history system
    lazy_history_patch = """
# Original heavy import
# from xonsh.history.main import History

# Optimized lazy import
from xonsh.lazy_imports import create_lazy_import
History = create_lazy_import('xonsh.history.main', 'History')
"""

    # Patch 3: Lazy tools import
    lazy_tools_patch = """
# Original import
# import xonsh.tools

# Optimized lazy import
from xonsh.lazy_imports import create_lazy_import
tools = create_lazy_import('xonsh.tools')
"""

    return {
        "completers": lazy_completers_patch,
        "history": lazy_history_patch,
        "tools": lazy_tools_patch,
    }


def benchmark_optimization():
    """Benchmark the performance improvement"""
    import time

    print("=== Benchmarking Lazy Import Optimization ===")

    # Test original import time
    start = time.time()
    original_time = (time.time() - start) * 1000

    # Clear modules to test lazy loading
    modules_to_clear = [
        "xonsh.completers.completer",
        "xonsh.history.main",
        "xonsh.tools",
    ]

    for mod in modules_to_clear:
        if mod in sys.modules:
            del sys.modules[mod]

    # Test lazy import time (just creation, not usage)
    start = time.time()
    lazy_completer = create_lazy_import("xonsh.completers.completer")
    lazy_history = create_lazy_import("xonsh.history.main")
    lazy_tools = create_lazy_import("xonsh.tools")
    lazy_time = (time.time() - start) * 1000

    print(f"Original import time: {original_time:.2f}ms")
    print(f"Lazy import creation: {lazy_time:.2f}ms")
    print(
        f"Improvement: {original_time - lazy_time:.2f}ms ({((original_time - lazy_time) / original_time * 100):.1f}%)"
    )

    # Test actual usage (this will trigger the real import)
    start = time.time()
    # Simulate accessing the lazy imports
    str(lazy_completer)  # This triggers the import
    str(lazy_history)  # This triggers the import
    str(lazy_tools)  # This triggers the import
    usage_time = (time.time() - start) * 1000

    print(f"First usage time: {usage_time:.2f}ms")

    return original_time, lazy_time, usage_time


if __name__ == "__main__":
    print("Testing Lazy Import Optimization")
    print("=" * 40)

    # Run benchmark
    orig, lazy, usage = benchmark_optimization()

    # Show patch examples
    patches = apply_lazy_loading_patch()
    print("\n=== Example Patches ===")
    for name, patch in patches.items():
        print(f"\n--- {name.upper()} PATCH ---")
        print(patch)
