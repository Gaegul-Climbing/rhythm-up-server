from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.accounts.models import User

SIGNUP_REQUEST = {
    "email": "member@example.com",
    "password": "correct-password",
    "name": "연습생",
    "phone": "010-1234-5678",
}


async def signup(client: AsyncClient) -> None:
    response = await client.post("/auth/signup", json=SIGNUP_REQUEST)
    assert response.status_code == 201


async def test_signup_stores_normalized_user_and_hashed_password(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    request = {**SIGNUP_REQUEST, "email": "Member@Example.COM"}

    response = await client.post("/auth/signup", json=request)

    assert response.status_code == 201
    assert response.json()["email"] == "member@example.com"
    user = await db_session.scalar(select(User))
    assert user is not None
    assert user.password_hash != SIGNUP_REQUEST["password"]
    assert SIGNUP_REQUEST["password"] not in user.password_hash


async def test_signup_rejects_duplicate_email(client: AsyncClient) -> None:
    await signup(client)

    response = await client.post("/auth/signup", json=SIGNUP_REQUEST)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_already_registered"


async def test_login_and_get_current_user(client: AsyncClient) -> None:
    await signup(client)

    login_response = await client.post(
        "/auth/login",
        data={
            "username": SIGNUP_REQUEST["email"],
            "password": SIGNUP_REQUEST["password"],
        },
    )

    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    me_response = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == SIGNUP_REQUEST["email"]
    assert me_response.json()["name"] == SIGNUP_REQUEST["name"]


async def test_login_rejects_wrong_password(client: AsyncClient) -> None:
    await signup(client)

    response = await client.post(
        "/auth/login",
        data={"username": SIGNUP_REQUEST["email"], "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert response.headers["www-authenticate"] == "Bearer"


async def test_get_current_user_requires_valid_token(client: AsyncClient) -> None:
    response = await client.get(
        "/users/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_access_token"
