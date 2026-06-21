from fastapi import Depends, HTTPException
from app.utils.dependencies import get_current_user

# Role taxonomy used across all routes:
#   admin        — full system access, data governance, user management
#   doctor       — clinical read/write (EMR, notes, AI tools), own appointments
#   nurse        — same clinical access as doctor minus billing/export
#   receptionist — scheduling and billing, no clinical records
#   patient      — own records only (appointments, billing, EMR via /me)

def require_roles(allowed_roles: list[str]):
    """Return a FastAPI dependency that enforces role membership.

    Previously this parameter was named `allowerd_roles` (typo). The name
    has no runtime effect (Python doesn't validate kwarg names at call sites
    that use positional args), but it was misleading to every reader and to
    static analysis tools. Fixed here.
    """
    def dependency(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Access Forbidden")
        return current_user
    return dependency
