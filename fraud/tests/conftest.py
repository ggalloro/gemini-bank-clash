import os
import sys
import tempfile
import pytest
import jwt

FRAUD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if FRAUD_DIR not in sys.path:
    sys.path.insert(0, FRAUD_DIR)

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["FRAUD_DB"] = _tmp.name
os.environ["TOKEN_SECRET"] = "test-secret"
os.environ["LEDGER_URL"] = "http://ledger.test"

import app as app_module
import models


@pytest.fixture
def client():
    if os.path.exists(_tmp.name):
        os.remove(_tmp.name)
    models.init_db()
    flask_app = app_module.create_app()
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as c:
        yield c


@pytest.fixture
def auth_header():
    token = jwt.encode({"user_id": 1, "full_name": "Test User"}, "test-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}
