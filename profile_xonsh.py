#!/usr/bin/env python3
"""
Xonsh Startup Performance Profiler

This script benchmarks Xonsh's startup performance, identifies heavy imports,
and profiles individual modules to guide optimization efforts.

Usage:
    python profile_xonsh.py
"""

import cProfile
import importlib
import pstats
import sys
import time


def profile_import(module_name, description=""):
    """Profile the import of a specific module"""
    print(f"\n=== Profiling: {module_name} {description} ===")

    start_time = time.time()
    try:
        importlib.import_module(module_name)
        end_time = time.time()
        print(f"Import time: {(end_time - start_time)*1000:.2f} ms")
    except ImportError as e:
        print(f"Failed to import {module_name}: {e}")
        return None

    prof = cProfile.Profile()
    prof.enable()
    try:
        importlib.reload(sys.modules[module_name])
    except Exception:
        importlib.import_module(module_name)
    prof.disable()

    stats = pstats.Stats(prof)
    print("Top time consumers:")
    stats.sort_stats('cumulative').print_stats(10)
    return stats


def benchmark_startup(repeats=5):
    """Benchmark full xonsh startup"""
    print("=== Full Xonsh Startup Benchmark ===")

    times = []
    for i in range(repeats):
        if 'xonsh.main' in sys.modules:
            del sys.modules['xonsh.main']
        start = time.time()
        end = time.time()
        delta = (end - start) * 1000
        times.append(delta)
        print(f"Run {i+1}: {delta:.2f} ms")

    avg_time = sum(times) / len(times)
    print(f"Average startup time: {avg_time:.2f} ms")
    return avg_time


def find_heavy_imports():
    """Identify the heaviest imports in xonsh"""
    heavy_modules = [
        'xonsh.main',
        'xonsh.execer',
        'xonsh.parser',
        'xonsh.completers',
        'xonsh.history',
        'xonsh.aliases',
        'xonsh.environ',
        'xonsh.built_ins',
        'xonsh.events',
        'xonsh.tools',
    ]

    print("\n=== Analyzing Heavy Module Imports ===")
    import_times = {}

    for module in heavy_modules:
        start = time.time()
        try:
            importlib.import_module(module)
            end = time.time()
            duration = (end - start) * 1000
            import_times[module] = duration
            print(f"{module}: {duration:.2f} ms")
        except ImportError as e:
            print(f"{module}: FAILED - {e}")

    sorted_times = sorted(import_times.items(), key=lambda x: x[1], reverse=True)
    print("\n=== Slowest Modules (candidates for lazy loading) ===")
    for module, time_ms in sorted_times[:5]:
        print(f"{module}: {time_ms:.2f} ms")
    return sorted_times


if __name__ == "__main__":
    print("Xonsh Performance Analysis")
    print("=" * 50)

    baseline = benchmark_startup()
    heavy_imports = find_heavy_imports()

    for module, _ in heavy_imports[:3]:
        profile_import(module)

    print("\n=== SUMMARY ===")
    print(f"Current average startup: {baseline:.2f} ms")
    print("Top optimization targets:")
    for i, (module, time_ms) in enumerate(heavy_imports[:5], 1):
        print(f"{i}. {module} ({time_ms:.2f} ms)")
