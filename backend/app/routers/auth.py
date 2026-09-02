"""Login / registration. Passwords are hashed with bcrypt and never returned."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from ..deps import CurrentUser, DbSession
from ..models import User, UserRole
from ..schemas import LoginRequest, TokenResponse, UserCreate, UserOut
from ..security import PasswordPolicyError, create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue(user: User) -> TokenResponse:
    token, expires_in = create_access_token(user.id, user.role.value)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: DbSession) -> TokenResponse:
    email = payload.email.lower().strip()
    existing = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists. Try signing in instead.",
        )

    # The very first account to be created owns the shop.
    is_first_user = db.execute(select(func.count(User.id))).scalar_one() == 0
    role = UserRole.owner if is_first_user else payload.role

    try:
        password_hash = hash_password(payload.password)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user = User(name=payload.name.strip(), email=email, password_hash=password_hash, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    email = payload.email.lower().strip()
    user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    # Same message either way so the endpoint cannot be used to enumerate emails.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is not correct.",
        )
    return _issue(user)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout() -> dict:
    """Stateless JWT: the client discards the token. Kept for a clean UI flow."""
    return {"detail": "Signed out."}


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
