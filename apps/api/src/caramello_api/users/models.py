from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from caramello_api.shared.base import Base

if TYPE_CHECKING:
    from caramello_api.families.models import Family, FamilyInvitation


class User(Base):
    """Represents a system user, provisioned on first authentication via Keycloak."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    uuid: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False, default=uuid4)
    idp_sub: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    families: Mapped[list[Family]] = relationship(
        secondary="family_member", back_populates="members", overlaps="user,family"
    )
    sent_invitations: Mapped[list[FamilyInvitation]] = relationship(back_populates="inviter")
