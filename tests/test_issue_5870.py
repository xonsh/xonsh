"""
Regression test for GitHub issue #5870.

Issue: $PATH is not an EnvPath when xonsh is initialized with --no-env

This test ensures that the PATH environment variable is always usable
with EnvPath methods like .prepend() regardless of how xonsh is started.
"""
import subprocess
import sys
import tempfile
import os
import pytest

from xonsh.environ import PATH_DEFAULT
from xonsh.tools import EnvPath


def test_path_default_conversion():
    """Test the exact fix: EnvPath(PATH_DEFAULT) vs list(PATH_DEFAULT)."""
    # This tests the specific line that was changed
    correct_path = EnvPath(PATH_DEFAULT)  # The fix
    buggy_path = list(PATH_DEFAULT)       # The original bug
    
    # Verify the fix works
    assert isinstance(correct_path, EnvPath), "EnvPath(PATH_DEFAULT) should create EnvPath"
    assert hasattr(correct_path, 'prepend'), "Fixed PATH should have prepend method"
    
    # Verify the bug would have failed
    assert isinstance(buggy_path, list), "list(PATH_DEFAULT) creates plain list"
    assert not hasattr(buggy_path, 'prepend'), "Buggy PATH lacks prepend method"


def test_path_prepend_functionality():
    """Test that EnvPath.prepend() works as expected."""
    path = EnvPath(PATH_DEFAULT)
    original_length = len(path)
    test_path = '/test/issue/5870/prepend'
    
    # This is what users expect to work
    path.prepend(test_path)
    assert path[0] == test_path, "prepend should add to front"
    assert len(path) == original_length + 1, "prepend should increase length"
    
    # Clean up
    path.remove(test_path)
    assert len(path) == original_length, "remove should restore length"


@pytest.mark.slow  
def test_no_env_integration():
    """Integration test: --no-env flag should not break PATH.prepend()"""
    
    # Script that reproduces the original user issue
    test_script = '''
# Test the exact functionality that was broken
print("Testing PATH.prepend() with --no-env flag")
print("PATH type:", type($PATH).__name__)

try:
    # This would fail with AttributeError before the fix
    $PATH.prepend("/integration/test")
    print("SUCCESS: PATH.prepend() works!")
    
    # Verify it was actually added
    if "/integration/test" in $PATH:
        print("VERIFIED: Path was added correctly")
    else:
        print("ERROR: Path was not added")
        exit(1)
        
except AttributeError as e:
    print("FAILED:", str(e))
    print("This means the bug still exists!")
    exit(1)
except Exception as e:
    print("OTHER_ERROR:", str(e))
    exit(1)
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xsh', delete=False) as f:
        f.write(test_script)
        script_path = f.name
    
    try:
        # Run with --no-env (this is where the bug occurred)
        result = subprocess.run([
            sys.executable, '-m', 'xonsh', '--no-env', script_path
        ], capture_output=True, text=True, timeout=30)
        
        # Check results
        assert result.returncode == 0, f"Script failed with: {result.stderr}"
        assert "SUCCESS" in result.stdout, "PATH.prepend() should work"
        assert "VERIFIED" in result.stdout, "Path should be added correctly"
        
        # Make sure we didn't get the old error
        assert "AttributeError" not in result.stderr, "Should not get AttributeError"
        assert "'list' object has no attribute 'prepend'" not in result.stderr, "Bug should be fixed"
        
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)


def test_normal_mode_still_works():
    """Ensure the fix doesn't break normal xonsh usage."""
    
    test_script = '''
print("Testing PATH in normal mode")
try:
    original_first = $PATH[0] if $PATH else "EMPTY"
    $PATH.prepend("/normal/mode/test")
    print("SUCCESS: Normal mode works")
    # Clean up
    $PATH.remove("/normal/mode/test")
except Exception as e:
    print("FAILED:", str(e))
    exit(1)
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xsh', delete=False) as f:
        f.write(test_script)
        script_path = f.name
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'xonsh', script_path
        ], capture_output=True, text=True, timeout=30)
        
        assert result.returncode == 0, f"Normal mode failed: {result.stderr}"
        assert "SUCCESS" in result.stdout, "Normal mode should still work"
        
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)


if __name__ == "__main__":
    print("Running regression tests for GitHub issue #5870")
    print("=" * 60)
    
    tests = [
        test_path_default_conversion,
        test_path_prepend_functionality,
        test_no_env_integration,
        test_normal_mode_still_works
    ]
    
    for test_func in tests:
        try:
            print(f"Running {test_func.__name__}...")
            test_func()
            print(f"✅ {test_func.__name__}")
        except Exception as e:
            print(f"❌ {test_func.__name__}: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    print("\n🎉 All regression tests passed!")
    print("Issue #5870 appears to be fixed correctly.")
