from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApplicationError
from app.domains.accounts.models import User
from app.domains.accounts.repository import add_user, get_user_by_email
from app.domains.accounts.schemas import SignUpRequest
from app.domains.accounts.security import hash_password, verify_password


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def register_user(session: AsyncSession, request: SignUpRequest) -> User:
    email = normalize_email(str(request.email))
    if await get_user_by_email(session, email) is not None:
        raise ApplicationError(
            code="email_already_registered",
            message="이미 가입된 이메일입니다.",
            status_code=409,
        )

    user = User(
        email=email,
        password_hash=hash_password(request.password),
        name=request.name,
        phone=request.phone,
    )
    add_user(session, user)

    try:
        await session.commit()
    except IntegrityError as exception:
        await session.rollback()
        raise ApplicationError(
            code="email_already_registered",
            message="이미 가입된 이메일입니다.",
            status_code=409,
        ) from exception

    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(session, normalize_email(email))
    if user is None or not verify_password(password, user.password_hash):
        raise ApplicationError(
            code="invalid_credentials",
            message="이메일 또는 비밀번호가 올바르지 않습니다.",
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
