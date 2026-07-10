from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.errors import ApplicationError
from app.database.dependencies import SessionDependency
from app.domains.accounts.models import User
from app.domains.accounts.repository import get_user_by_id
from app.domains.accounts.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

TokenDependency = Annotated[str, Depends(oauth2_scheme)]


def unauthorized_error() -> ApplicationError:
    return ApplicationError(
        code="invalid_access_token",
        message="유효하지 않은 인증 정보입니다.",
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: TokenDependency,
    session: SessionDependency,
) -> User:
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise unauthorized_error()
        user_id = UUID(subject)
    except (jwt.InvalidTokenError, ValueError) as exception:
        raise unauthorized_error() from exception

    user = await get_user_by_id(session, user_id)
    if user is None:
        raise unauthorized_error()
    return user


CurrentUserDependency = Annotated[User, Depends(get_current_user)]
