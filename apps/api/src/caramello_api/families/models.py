from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from caramello_api.shared.base import Base
from caramello_api.users.models import User


class Family(Base):
    """Represents a family group in the system."""

    __tablename__ = "family"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    uuid: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    members: Mapped[list[User]] = relationship(
        secondary="family_member", back_populates="families", overlaps="user,family"
    )
    invitations: Mapped[list[FamilyInvitation]] = relationship(back_populates="family")


class FamilyMember(Base):
    """
    Association table connecting Users and Families, defining the role of each member.
    """

    __tablename__ = "family_member"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), primary_key=True, nullable=False
    )
    family_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("family.id"), primary_key=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    user: Mapped[User] = relationship(overlaps="families,members")
    family: Mapped[Family] = relationship(overlaps="families,members")


class FamilyInvitation(Base):
    """Pré-registro de membro de família por email (D-01)."""

    __tablename__ = "family_invitation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, nullable=False)
    uuid: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False, default=uuid4)
    family_id: Mapped[int] = mapped_column(Integer, ForeignKey("family.id"), nullable=False)
    inviter_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_login")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    family: Mapped[Family] = relationship(back_populates="invitations")
    inviter: Mapped[User] = relationship(back_populates="sent_invitations")
