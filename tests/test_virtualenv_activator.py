import sys
from pathlib import Path
from subprocess import check_output

from xonsh.pytest.tools import ON_WINDOWS


def test_xonsh_activator(tmp_path):
    # Create virtualenv
    venv_dir = tmp_path / "venv"
    assert b"XonshActivator" in check_output(
        [sys.executable, "-m", "virtualenv", str(venv_dir)]
    )
    assert venv_dir.is_dir()

    # Check activation script created
    if ON_WINDOWS:
        bin_path = venv_dir / "Scripts"
    else:
        bin_path = venv_dir / "bin"
    activate_path = bin_path / "activate.xsh"
    assert activate_path.is_file()

    # Sanity
    original_python = check_output(
        [
            sys.executable,
            "-m",
            "xonsh",
            "-c",
            "import shutil; shutil.which('python') or shutil.which('python3')",
        ]
    ).decode()
    assert Path(original_python).parent != bin_path

    # Activate
    venv_python = check_output(
        [sys.executable, "-m", "xonsh", "-c", f"source {activate_path}; which python"]
    ).decode()
    assert Path(venv_python).parent == bin_path

    # Deactivate
    deactivated_python = check_output(
        [
            sys.executable,
            "-m",
            "xonsh",
            "-c",
            f"source {activate_path}; deactivate; "
            "import shutil; shutil.which('python') or shutil.which('python3')",
        ]
    ).decode()
    assert deactivated_python == original_python
