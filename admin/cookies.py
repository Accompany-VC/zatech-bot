"""Secure cookie managment utilities."""

import os
from fastapi import Response

def is_prod() -> bool:
    """Check if running in production environment."""

    return os.getenv("ENVIRONMENT", "development") == "production"

def set_auth_cookie(response: Response, token: str) -> None:
    """Set secure authentication cookie on response."""

    secure = is_prod() # Check dev/prod environment
    response.set_cookie(
        key="firebase_token",
        value=token,
        max_age=3600, # 1 hour
        path="/",
        httponly=True,
        secure=secure,
        samesite="strict",
    )

def clear_auth_cookie(response: Response) -> None:
    """Clear authentication cookie from response."""

    secure = is_prod() # Check dev/prod environment
    response.delete_cookie(
        key="firebase_token",
        path="/",
        httponly=True,
        secure=secure,
        samesite="strict",
    )
