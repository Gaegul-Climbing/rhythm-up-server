from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.database.dependencies import SessionDependency
from app.domains.accounts.dependencies import CurrentUserDependency
from app.domains.accounts.schemas import SignUpRequest, TokenResponse, UserResponse
from app.domains.accounts.security import create_access_token
from app.domains.accounts.service import authenticate_user, register_user

router = APIRouter()


@router.post("/auth/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignUpRequest, session: SessionDependency) -> UserResponse:
    user = await register_user(session, request)
    return UserResponse.model_validate(user)


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDependency,
) -> TokenResponse:
    user = await authenticate_user(session, form.username, form.password)
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/users/me", response_model=UserResponse)
async def get_me(current_user: CurrentUserDependency) -> UserResponse:
    return UserResponse.model_validate(current_user)
