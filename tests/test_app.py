import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base, URL_DATABASE
from main import app, get_db


SQLALCHEMY_DATABASE_URL = URL_DATABASE

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_function():
    if not is_safe_test_database(SQLALCHEMY_DATABASE_URL):
        raise RuntimeError("Refusing to reset a non-test database.")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def is_safe_test_database(database_url):
    return (
        database_url.startswith("sqlite")
        or "test" in database_url.rsplit("/", 1)[-1].lower()
    )


def register_user(username="player1", email="player1@example.com", password="secret123"):
    return client.post(
        "/register/",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )


def login_user(username="player1", password="secret123"):
    response = client.post(
        "/login/",
        data={
            "username": username,
            "password": password,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_user_hashes_password():
    response = register_user()

    assert response.status_code == 200
    assert response.json() == {"username": "player1 succesfully added"}

    db = TestingSessionLocal()
    user = db.query(models.User).filter(models.User.username == "player1").first()
    db.close()

    assert user is not None
    assert user.email == "player1@example.com"
    assert user.password != "secret123"


def test_register_rejects_duplicate_email():
    assert register_user().status_code == 200

    response = register_user(username="player2")

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already exists"


def test_login_and_read_current_user():
    assert register_user().status_code == 200
    token = login_user()

    response = client.get("/users/me/", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["username"] == "player1"
    assert response.json()["email"] == "player1@example.com"


def test_games_require_authentication():
    response = client.get("/games/")

    assert response.status_code == 401


def test_add_game_and_list_library():
    assert register_user().status_code == 200
    token = login_user()

    create_response = client.post(
        "/games/",
        headers=auth_headers(token),
        json={
            "title": "Elden Ring",
            "platform": "PC",
            "genre": "Action RPG",
            "release_year": 2022,
            "status": "playing",
        },
    )
    list_response = client.get("/games/", headers=auth_headers(token))

    assert create_response.status_code == 201
    assert create_response.json()["title"] == "Elden Ring"
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["title"] == "Elden Ring"


def test_update_game_status():
    assert register_user().status_code == 200
    token = login_user()
    game = client.post(
        "/games/",
        headers=auth_headers(token),
        json={"title": "Hades"},
    ).json()

    response = client.put(
        f"/games/{game['id']}/status",
        headers=auth_headers(token),
        json={"status": "completed"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_delete_game():
    assert register_user().status_code == 200
    token = login_user()
    game = client.post(
        "/games/",
        headers=auth_headers(token),
        json={"title": "Celeste"},
    ).json()

    delete_response = client.delete(
        f"/games/{game['id']}",
        headers=auth_headers(token),
    )
    list_response = client.get("/games/", headers=auth_headers(token))

    assert delete_response.status_code == 200
    assert delete_response.json() == {"detail": "Game deleted"}
    assert list_response.json() == []


def test_user_cannot_update_another_users_game():
    assert register_user().status_code == 200
    player1_token = login_user()
    player1_game = client.post(
        "/games/",
        headers=auth_headers(player1_token),
        json={"title": "Outer Wilds"},
    ).json()

    assert register_user(
        username="player2",
        email="player2@example.com",
        password="secret456",
    ).status_code == 200
    player2_token = login_user(username="player2", password="secret456")

    response = client.put(
        f"/games/{player1_game['id']}/status",
        headers=auth_headers(player2_token),
        json={"status": "dropped"},
    )

    assert response.status_code == 404
