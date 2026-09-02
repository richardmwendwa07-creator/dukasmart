"""Shared FastAPI dependencies: current user + role gates."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, UserRole
from .security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Your session has expired or is invalid. Please sign in again.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise CREDENTIALS_ERROR
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise CREDENTIALS_ERROR from None

    subject = payload.get("sub")
    if subject is None:
        raise CREDENTIALS_ERROR
    user = db.get(User, int(subject))
    if user is None:
        raise CREDENTIALS_ERROR
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]


def require_owner(user: CurrentUser) -> User:
    """Owner-only actions: budgets, recommendations, product/supplier setup."""
    if user.role != UserRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the shop owner can do this. Ask the owner to sign in.",
        )
    return user


OwnerUser = Annotated[User, Depends(require_owner)]
