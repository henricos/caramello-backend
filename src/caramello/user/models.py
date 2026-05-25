from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from caramello.family.models import Family, FamilyInvitation


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

    families: list[Family] = Relationship(back_populates="members")
    sent_invitations: list[FamilyInvitation] = Relationship(back_populates="inviter")


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


# ---------------------------------------------------------------------------
# Late-bind do link_model para o relacionamento M:M User <-> Family.
# FamilyMember (definido em caramello.family.models) não pode ser importado
# diretamente acima porque criaria um ciclo: family → user → family.
# A solução é importar FamilyMember apenas aqui, após a definição de User,
# e associá-lo via RelationshipInfo.link_model.
# Isso garante que SQLModel/SQLAlchemy saiba montar a query M:M corretamente.
# ---------------------------------------------------------------------------
from caramello.family.models import FamilyMember as _FamilyMember  # noqa: E402

User.__sqlmodel_relationships__["families"].link_model = _FamilyMember
