import os

os.environ["EVORIUM_LOG_FILE"] = ""  # tests must never write to the real evorium.log

import pytest
from evorium import backoff

@pytest.fixture(autouse=True)
def isolated_provider_pause():
    backoff.reset()
    yield
    backoff.reset()
