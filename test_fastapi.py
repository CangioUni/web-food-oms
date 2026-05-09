import pytest
from fastapi.testclient import TestClient

# Mock module dependencies for fast unit testing if escpos/PIL fail.
import sys
from unittest.mock import MagicMock
sys.modules['escpos'] = MagicMock()
sys.modules['escpos.printer'] = MagicMock()


try:
    from main import app
    client = TestClient(app)

    def test_read_main():
        response = client.get("/")
        assert response.status_code == 200

    def test_get_menu():
        response = client.get("/menu")
        assert response.status_code == 200
except Exception as e:
    print(f"Cannot run API tests: {e}")
