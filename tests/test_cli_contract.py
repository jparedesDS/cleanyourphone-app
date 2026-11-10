import os

import pytest

from cleanyourphone_app.services.cli import CliClient

CLI = os.environ.get("CLEANYOURPHONE_CLI")


@pytest.mark.skipif(
    not CLI,
    reason="set CLEANYOURPHONE_CLI to the frozen cleanyourphone sidecar",
)
def test_frozen_sidecar_reports_the_pinned_version():
    client = CliClient([CLI])
    assert client.version() == "CleanYourPhone 0.3.0"
