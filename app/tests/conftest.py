import pytest
from fastapi.testclient import TestClient

from main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def db_session():
    # Import here to avoid circular imports during test collection
    from app.database.connection import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()