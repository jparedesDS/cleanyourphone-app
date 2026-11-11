import subprocess
import sys

from cleanyourphone_app.version import __version__


def test_version_is_0_2_3():
    assert __version__ == "0.2.3"


def test_module_version_flag():
    result = subprocess.run(
        [sys.executable, "-m", "cleanyourphone_app", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "CleanYourPhone app 0.2.3"
