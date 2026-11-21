import os
import tempfile
import pytest
from config import Config
from app import create_app, db

@pytest.fixture
def client(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    old_uri = Config.SQLALCHEMY_DATABASE_URI
    old_secret = Config.SECRET_KEY
    Config.SQLALCHEMY_DATABASE_URI = "sqlite:///" + path
    Config.SECRET_KEY = "test-secret"
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    Config.SQLALCHEMY_DATABASE_URI = old_uri
    Config.SECRET_KEY = old_secret
    os.unlink(path)

def register_and_login(client):
    return client.post("/register", data={"name":"Test User", "email":"test@example.com", "password":"password123", "confirm_password":"password123"}, follow_redirects=True)

def test_register_dashboard_and_api(client):
    response = register_and_login(client)
    assert response.status_code == 200
    assert b"Water consumption trend" in response.data
    assert client.get("/api/summary").status_code == 200
    assert client.get("/api/forecast").status_code == 200

def test_login_required(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.location

def test_duplicate_email_and_password_validation(client):
    register_and_login(client)
    response = client.post("/register", data={"name":"Other", "email":"test@example.com", "password":"password123", "confirm_password":"password123"}, follow_redirects=True)
    assert b"already exists" in response.data
