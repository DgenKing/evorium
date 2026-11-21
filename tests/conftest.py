import os

os.environ["EVORIUM_LOG_FILE"] = ""  # tests must never write to the real evorium.log

import pytest
from evorium import backoff

@pytest.fixture(autouse=True)
def isolated_provider_pause():
    backoff.reset()
    yield
    backoff.reset()


@pytest.fixture(autouse=True)
def no_dashboard_password(monkeypatch):
    # The machine's own config.py may set DASHBOARD_PASSWORD (the G4 server does); tests must not depend on it.
    # Auth tests set their own password with monkeypatch, which overrides this.
    from evorium import main
    monkeypatch.setattr(main, "DASHBOARD_PASSWORD", "")
    monkeypatch.setattr(main, "ACCOUNTS", {})
