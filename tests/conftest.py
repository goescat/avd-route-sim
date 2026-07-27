import pytest

import app as app_module


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    app_module._sim = None
    with app_module.app.test_client() as test_client:
        yield test_client
    app_module._sim = None
