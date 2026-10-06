from functools import lru_cache

from fastapi import Depends, HTTPException

from app.core.security import User, get_user
from app.services.pipeline import HLDService


@lru_cache
def get_service() -> HLDService:
    return HLDService()


def ensure_document_access(user: User, document_id: str, minimum: str = "viewer") -> dict:
    """Role check plus project isolation for one document; returns its metadata."""
    if not user.has_role(minimum):
        raise HTTPException(403, f"Requires role '{minimum}' or higher.")
    meta = get_service().metadata(document_id)
    if not user.can_access(meta.get("project", "default")):
        raise HTTPException(403, "You do not have access to this document's project.")
    return meta


class DocAccess:
    """Dependency for routes with a {document_id} path parameter."""

    def __init__(self, minimum: str = "viewer"):
        self.minimum = minimum

    def __call__(self, document_id: str, user: User = Depends(get_user)) -> User:
        ensure_document_access(user, document_id, self.minimum)
        return user


def audit(user: User, action: str, resource: str = "", detail: str = "") -> None:
    get_service().store.log_audit(user.name, user.role, action, resource, detail)
