import os
from pathlib import Path
import pytest
import requests

STATEMENTS_URL = os.environ.get("STATEMENTS_URL", "http://localhost:8083")
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture(scope="session")
def base_url():
    return STATEMENTS_URL


@pytest.fixture(scope="session")
def client():
    class StatementsClient:
        def __init__(self, base_url: str):
            self.base_url = base_url.rstrip("/")
            self.session = requests.Session()

        def get(self, path: str, **kwargs):
            url = f"{self.base_url}/{path.lstrip('/')}"
            return self.session.get(url, **kwargs)

    return StatementsClient(STATEMENTS_URL)
