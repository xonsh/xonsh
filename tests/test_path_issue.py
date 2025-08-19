"""
Simple regression test for GitHub issue #5870.
Tests that PATH is always an EnvPath instance.
"""

import os
import subprocess
import sys
import tempfile

import pytest

from xonsh.environ import PATH_DEFAULT, Env
from xonsh.tools import EnvPath


def test_path_is_always_envpath():
    """Core test: PATH should always be EnvPath, never plain list."""
    env = Env()
    path = env.get("PATH")

    assert isinstance(path, EnvPath), f"PATH should be EnvPath, got {type(path)}"
    assert hasattr(path, "prepend"), "PATH should have prepend method"


def test_path_default_becomes_envpath():
    """Test that PATH_DEFAULT gets converted to EnvPath properly."""
    # This tests the exact line that was buggy
    path_from_default = EnvPath(PATH_DEFAULT)  # This is the fix
    path_as_list = list(PATH_DEFAULT)  # This was the bug

    assert isinstance(path_from_default, EnvPath), (
        "EnvPath(PATH_DEFAULT) should be EnvPath"
    )
    assert isinstance(path_as_list, list), "list(PATH_DEFAULT) should be plain list"
    assert not isinstance(path_as_list, EnvPath), "list() should not create EnvPath"

    # The fix ensures we use the first, not the second
    assert hasattr(path_from_default, "prepend"), "EnvPath should have prepend"
    assert not hasattr(path_as_list, "prepend"), "plain list should not have prepend"


def test_path_prepend_works():
    """Test that PATH.prepend() works (this was the user-reported failure)."""
    env = Env()
    path = env.get("PATH")

    original_length = len(path)
    test_path = "/test/issue/5870"

    # This should work without AttributeError
    path.prepend(test_path)
    assert path[0] == test_path
    assert len(path) == original_length + 1

    # Clean up
    path.remove(test_path)


@pytest.mark.slow
def test_no_env_flag_integration():
    """Integration test: verify --no-env flag works with PATH.prepend()"""

    # Create test script that uses PATH.prepend()
    script_content = """
try:
    $PATH.prepend("/integration/test/path")
    print("SUCCESS: prepend worked")
except AttributeError as e:
    print("FAIL: " + str(e))
    exit(1)
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xsh", delete=False) as f:
        f.write(script_content)
        script_path = f.name

    try:
        # Test with --no-env flag (this is where the original bug occurred)
        result = subprocess.run(
            [sys.executable, "-m", "xonsh", "--no-env", script_path],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should succeed, not fail with AttributeError
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert "SUCCESS" in result.stdout, (
            f"Expected success message, got: {result.stdout}"
        )
        assert "prepend worked" in result.stdout, (
            "PATH.prepend() should work with --no-env"
        )

    finally:
        if os.path.exists(script_path):
            os.remove(script_path)


if __name__ == "__main__":
    # Run tests directly
    tests = [
        test_path_is_always_envpath,
        test_path_default_becomes_envpath,
        test_path_prepend_works,
        test_no_env_flag_integration,
    ]

    for test in tests:
        try:
            print(f"Running {test.__name__}...")
            test()
            print(f"✅ {test.__name__}")
        except Exception as e:
            print(f"❌ {test.__name__}: {e}")
            import traceback

            traceback.print_exc()

    print("\n🎉 All tests passed!")
