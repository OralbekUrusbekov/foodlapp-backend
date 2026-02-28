import uuid
import pytest
from httpx import AsyncClient
from app.schemas.auth_dto import UserUpdateRequest
from app.models.user import User
from app.service.auth_service import AuthService
from main import app


def random_email():
    return f"test_user_{uuid.uuid4().hex[:8]}@example.com"


def test_update_me_direct(db_session):
    # Create a user via AuthService (this uses the same logic as /register)
    email = random_email()
    user = AuthService.register_user(
        db=db_session,
        full_name="Direct Test User",
        email=email,
        password="password123"
    )

    # Call the route function directly to update profile
    from app.api.auth import update_me
    payload = UserUpdateRequest(avatar_url="https://example.com/a.png", bio="bio", address="addr")

    updated = update_me(data=payload, db=db_session, current_user=user)

    assert updated.avatar_url == "https://example.com/a.png"
    assert updated.bio == "bio"
    assert updated.address == "addr"

    # cleanup
    db_session.delete(user)
    db_session.commit()


@pytest.mark.anyio
async def test_profile_update_via_http(db_session):
    # Register and authenticate via HTTP ASGI client
    email = random_email()
    register_payload = {
        "full_name": "Async Test User",
        "email": email,
        "password": "password123"
    }

    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        resp = await ac.post("/api/auth/register", json=register_payload)
        assert resp.status_code == 201
        tokens = resp.json()
        access = tokens["access_token"]

        headers = {"Authorization": f"Bearer {access}"}

        # Update profile
        update_payload = {"avatar_url": "https://example.com/async.png", "bio": "async bio", "address": "async addr"}
        put_resp = await ac.put("/api/auth/me", json=update_payload, headers=headers)
        assert put_resp.status_code == 200
        updated = put_resp.json()
        assert updated["avatar_url"] == update_payload["avatar_url"]
        assert updated["bio"] == update_payload["bio"]
        assert updated["address"] == update_payload["address"]

    # Confirm DB record updated
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.avatar_url == update_payload["avatar_url"]

    # cleanup
    db_session.delete(user)
    db_session.commit()