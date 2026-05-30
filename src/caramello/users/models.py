from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from caramello.families.models import Family, FamilyInvitation


class User(SQLModel, table=True):
    """Represents a system user, provisioned on first authentication via Keycloak."""

    __tablename__ = "user"

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    idp_sub: str = Field(unique=True, nullable=False)
    email: EmailStr = Field(unique=True, nullable=False)
    name: str = Field(max_length=100, nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    families: list["Family"] = Relationship(
        back_populates="members",
        sa_relationship_kwargs={
            "secondary": "family_member",
            "overlaps": "user,family",
        },
    )  # noqa: UP037
    sent_invitations: list["FamilyInvitation"] = Relationship(back_populates="inviter")  # noqa: UP037


class UserRead(SQLModel):
    uuid: UUID
    idp_sub: str
    email: EmailStr
    name: str
    created_at: datetime
    updated_at: datetime


class UserCreate(SQLModel):
    idp_sub: str
    email: EmailStr
    name: str


class UserUpdate(SQLModel):
    idp_sub: str | None = None
    email: EmailStr | None = None
    name: str | None = None
