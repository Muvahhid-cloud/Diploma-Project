"""Import every ORM model so Base.metadata is complete (used by Alembic and tests)."""

from app.modules.auth.models import RefreshToken, User
from app.modules.projects.models import Project

__all__ = ["Project", "RefreshToken", "User"]
