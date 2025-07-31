#!/usr/bin/env python3
"""
Performance testing script for xonsh lazy import optimization
Run this to validate the performance improvements
"""

import time
import sys
import importlib
import statistics
from contextlib import contextmanager


@contextmanager
def timing(description="Operation"):
    """Context manager for timing operations."""
    start = time.time()
    yield
    end = time.time()
    print(f"{description}: {(end - start) * 1000:.2f}ms")


def clear_xonsh_modules():
    """Clear xonsh modules from sys.modules to ensure fresh imports."""
    to_remove = [name for name in sys.modules.keys() if name.startswith('xonsh')]
    for name in to_remove:
        del sys.modules[name]


def benchmark_startup(num_runs=5):
    """Benchmark xonsh startup time."""
    print(f"=== Benchmarking Xonsh Startup ({num_runs} runs) ===")
    
    times = []
    for i in range(num_runs):
        clear_xonsh_modules()
        
        start = time.time()
        import xonsh.main
        end = time.time()
        
        run_time = (end - start) * 1000
        times.append(run_time)
        print(f"Run {i+1}: {run_time:.2f}ms")
    
    avg_time = statistics.mean(times)
    std_dev = statistics.stdev(times) if len(times) > 1 else 0
    
    print(f"Average: {avg_time:.2f}ms (±{std_dev:.2f}ms)")
    return avg_time, std_dev


def test_lazy_imports():
    """Test that lazy imports work correctly."""
    print("\n=== Testing Lazy Import Functionality ===")
    
    # Test lazy module import
    from xonsh.lazy_imports import lazy_import_module, lazy_import_object
    
    print("Testing lazy module import...")
    with timing("Lazy module creation"):
        lazy_tools = lazy_import_module('xonsh.tools')
    
    print(f"Lazy module before access: {lazy_tools}")
    
    with timing("First access (triggers import)"):
        # This should trigger the actual import
        hasattr(lazy_tools, 'unthreadable')
    
    print(f"Lazy module after access: {lazy_tools}")
    
    # Test lazy object import  
    print("\nTesting lazy object import...")
    with timing("Lazy object creation"):
        LazyCompleter = lazy_import_object('xonsh.completers.completer', 'Completer')
    
    print(f"Lazy object before access: {LazyCompleter}")
    
    # This should trigger the import
    with timing("First access (triggers import)"):
        completer_class = LazyCompleter
        # Access a method to ensure it's fully loaded
        str(completer_class)
    
    print(f"Lazy object after access: {LazyCompleter}")


def compare_import_methods():
    """Compare direct imports vs lazy imports."""
    print("\n=== Comparing Import Methods ===")
    
    # Test direct imports
    modules_to_test = [
        'xonsh.completers.bash_completion',
        'xonsh.completers.python', 
        'xonsh.history.main',
        'xonsh.tools',
    ]
    
    # Clear modules first
    clear_xonsh_modules()
    
    # Time direct imports
    with timing("Direct imports"):
        for module in modules_to_test:
            try:
                importlib.import_module(module)
            except ImportError:
                print(f"Warning: Could not import {module}")
    
    # Clear modules again
    clear_xonsh_modules()
    
    # Time lazy import creation (should be much faster)
    from xonsh.lazy_imports import lazy_import_module
    
    with timing("Lazy import creation"):
        lazy_modules = []
        for module in modules_to_test:
            lazy_modules.append(lazy_import_module(module))
    
    print(f"Created {len(lazy_modules)} lazy imports")
    
    # Time first access (this triggers actual imports)
    with timing("First access to lazy imports"):
        for lazy_mod in lazy_modules:
            try:
                # Just check if module has any attribute to trigger import
                dir(lazy_mod)
            except:
                pass


def validate_functionality():
    """Validate that lazy imports don't break functionality."""
    print("\n=== Validating Functionality ===")
    
    try:
        from xonsh.lazy_imports import lazy_import_object
        
        # Test that we can create and use a lazy History object
        LazyHistory = lazy_import_object('xonsh.history.main', 'History')
        
        # This should work without errors
        print("✓ Lazy History object created successfully")
        
        # Test accessing methods/attributes
        history_methods = dir(LazyHistory)
        print(f"✓ Can access History methods: {len(history_methods)} methods found")
        
        print("✓ All functionality tests passed")
        
    except Exception as e:
        print(f"✗ Functionality test failed: {e}")
        return False
    
    return True


def main():
    """Run all performance tests."""
    print("Xonsh Performance Optimization Test Suite")
    print("=" * 50)
    
    # 1. Test basic functionality
    if not validate_functionality():
        print("❌ Functionality tests failed - aborting")
        return
    
    # 2. Test lazy import behavior
    test_lazy_imports()
    
    # 3. Compare import methods
    compare_import_methods()
    
    # 4. Benchmark overall startup
    avg_time, std_dev = benchmark_startup()
    
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Average startup time: {avg_time:.2f}ms ±{std_dev:.2f}ms")
    
    # Provide improvement estimates
    if avg_time < 150:  # Arbitrary threshold
        print("✅ Good performance - under 150ms startup time")
    elif avg_time < 300:
        print("⚠️  Moderate performance - 150-300ms startup time")  
    else:
        print("❌ Slow performance - over 300ms startup time")
    
    print("\nTo measure improvement:")
    print("1. Run this script before applying the patch")
    print("2. Apply the lazy import optimization")  
    print("3. Run this script again")
    print("4. Compare the results")


if __name__ == "__main__":
    main()
