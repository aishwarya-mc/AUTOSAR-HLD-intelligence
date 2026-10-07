from fastapi import APIRouter, Depends, Query

from app.api.deps import get_service
from app.core.security import User, require_role

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("")
def audit_log(limit: int = Query(200, ge=1, le=1000), user: User = Depends(require_role("admin"))):
    """Who did what and when (admin only)."""
    return get_service().store.list_audit(limit)
