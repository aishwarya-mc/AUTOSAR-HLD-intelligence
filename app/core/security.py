from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from app.core.config import get_settings

ROLE_ORDER = {"viewer": 0, "reviewer": 1, "admin": 2}


@dataclass(frozen=True)
class User:
    name: str
    role: str
    projects: tuple[str, ...]  # ("*",) means every project

    def can_access(self, project: str) -> bool:
        return "*" in self.projects or project in self.projects

    def has_role(self, minimum: str) -> bool:
        return ROLE_ORDER[self.role] >= ROLE_ORDER[minimum]


ANONYMOUS_ADMIN = User("anonymous", "admin", ("*",))


def parse_api_keys(spec: str) -> dict[str, User]:
    """Parse API_KEYS="key:role:name[:projectA|projectB]" entries separated by commas."""
    users: dict[str, User] = {}
    for entry in filter(None, (e.strip() for e in spec.split(","))):
        parts = entry.split(":")
        if len(parts) < 3 or parts[1] not in ROLE_ORDER:
            raise ValueError(
                "API_KEYS entries must look like key:role:name[:project1|project2] "
                f"with role in {sorted(ROLE_ORDER)}"
            )
        projects = tuple(parts[3].split("|")) if len(parts) > 3 and parts[3] else ("*",)
        users[parts[0]] = User(parts[2], parts[1], projects)
    return users


def get_user(x_api_key: str | None = Header(default=None)) -> User:
    """Resolve the caller. With AUTH_ENABLED=false (local dev) everyone is an admin."""
    settings = get_settings()
    if not settings.auth_enabled:
        return ANONYMOUS_ADMIN
    keys = parse_api_keys(settings.api_keys)
    if not keys:
        raise HTTPException(500, "AUTH_ENABLED is true but API_KEYS is empty.")
    user = keys.get(x_api_key or "")
    if user is None:
        raise HTTPException(401, "Missing or invalid X-API-Key.")
    return user


def require_role(minimum: str):
    def dependency(user: User = Depends(get_user)) -> User:
        if not user.has_role(minimum):
            raise HTTPException(403, f"Requires role '{minimum}' or higher.")
        return user

    return dependency
