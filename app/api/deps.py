from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.models import Role, UserContext


def get_current_user(
    x_user_id: str | None = Header(default=None),
    x_role: str | None = Header(default=None),
    x_org_id: str | None = Header(default=None),
    x_region: str | None = Header(default=None),
) -> UserContext:
    role_str = x_role or "viewer"
    try:
        role = Role(role_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {role_str}",
        )

    return UserContext(
        user_id=x_user_id or "anonymous",
        role=role,
        org_id=x_org_id,
        region=x_region,
    )
