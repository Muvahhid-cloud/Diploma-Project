import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    building_type: Mapped[str] = mapped_column(
        String(64), default="single_family_house", server_default="single_family_house"
    )
    region_code: Mapped[str] = mapped_column(String(16))
    currency: Mapped[str] = mapped_column(String(3))
    rules_profile_id: Mapped[str] = mapped_column(String(80))
    # FK to project_versions is added when that table is introduced (Phase 1).
    current_version_id: Mapped[uuid.UUID | None] = mapped_column()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
