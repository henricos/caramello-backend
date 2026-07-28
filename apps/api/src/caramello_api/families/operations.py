# CARAMELLO-GENERATED: implemented
"""Operações de negócio do domínio families — Phase 4.

Cobre:
  - FAMILY-01: POST /families/registry (criar família + tornar-se owner)
  - FAMILY-02: GET  /families/families (listar minhas famílias)
  - FAMILY-03: GET  /families/families/{uuid} (detalhe se membro, 403 senão)
  - D-07:      POST /families/families/{uuid}/pre-register (owner pré-registra email)
  - D-07:      GET  /families/families/{uuid}/members (lista membros se membro)
  - FAMILY-07: DELETE /families/families/{uuid}/members/{user_uuid} (owner remove)

NÃO implementado nesta fase (D-04 — deferidos para M2):
  - FAMILY-04: POST /families/families/{uuid}/invitations (código convite reutilizável)
  - FAMILY-05: POST /families/invitations/{code}/join (solicitação de entrada)
  - FAMILY-06: PATCH /families/invitations/{id} (aprovar/rejeitar)
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello_api.families.models import (
    Family,
    FamilyCreate,
    FamilyInvitation,
    FamilyInvitationRead,
    FamilyMember,
    FamilyRead,
)
from caramello_api.shared.auth import get_current_user
from caramello_api.shared.database import get_session
from caramello_api.users.models import User

router = APIRouter(prefix="/families", tags=["Family"])


# ---------------------------------------------------------------------------
# Schemas locais (não fazem parte da geração DSL — específicos das operações)
# ---------------------------------------------------------------------------


class PreRegisterBody(BaseModel):
    """Body de POST /families/{uuid}/pre-register — só precisa do email do convidado."""

    email: EmailStr


class FamilyMemberRead(BaseModel):
    """Retorno de GET /families/{uuid}/members. Inclui user_uuid resolvido via JOIN."""

    user_uuid: UUID
    role: str
    joined_at: datetime


# ---------------------------------------------------------------------------
# Helpers de autorização (D-13 — verificação de role)
# ---------------------------------------------------------------------------


async def _require_owner(
    family_uuid: UUID,
    current_user: User,
    session: AsyncSession,
) -> tuple[Family, FamilyMember]:
    """Garante que o usuário é OWNER da família com o uuid dado.

    Retorna (family, member) se sim; raise 403 caso contrário.
    """
    result = await session.exec(
        select(Family, FamilyMember)
        .join(FamilyMember, FamilyMember.family_id == Family.id)  # type: ignore[arg-type]
        .where(
            Family.uuid == family_uuid,
            FamilyMember.user_id == current_user.id,
            FamilyMember.role == "owner",
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas owner pode realizar esta operação",
        )
    family, member = row
    return family, member


async def _require_member(
    family_uuid: UUID,
    current_user: User,
    session: AsyncSession,
) -> Family:
    """Garante que o usuário é MEMBRO (qualquer role) da família com o uuid dado.

    Retorna Family se sim; raise 403 caso contrário.
    """
    result = await session.exec(
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)  # type: ignore[arg-type]
        .where(
            Family.uuid == family_uuid,
            FamilyMember.user_id == current_user.id,
        )
    )
    family = result.first()
    if family is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não é membro desta família",
        )
    return family


# ---------------------------------------------------------------------------
# FAMILY-01: POST /families/registry
# ---------------------------------------------------------------------------


@router.post("/registry", response_model=FamilyRead, status_code=status.HTTP_201_CREATED)
async def registry_family(
    family_in: FamilyCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Family:
    """FAMILY-01: cria família e registra o usuário autenticado como owner."""
    # exclude_unset=True + exclude_none=True para não sobrescrever defaults do modelo
    # (ex: status="active" default em Family, que seria None se omitido em FamilyCreate)
    family_data = family_in.model_dump(exclude_none=True)
    db_family = Family.model_validate(family_data)
    session.add(db_family)
    # flush para obter db_family.id sem commitar — necessário para o FK do FamilyMember.
    # RESOLVED (Open Question 1 do 04-RESEARCH.md): session.flush() com SQLModel+asyncpg
    # é seguro para obter PK autoincrement antes do commit (padrão estabelecido).
    await session.flush()

    owner_member = FamilyMember(
        user_id=current_user.id,
        family_id=db_family.id,
        role="owner",
    )
    session.add(owner_member)
    await session.commit()
    await session.refresh(db_family)
    return db_family


# ---------------------------------------------------------------------------
# FAMILY-02: GET /families/families
# ---------------------------------------------------------------------------


@router.get(
    "/families",
    response_model=list[FamilyRead],
    operation_id="list_my_families",
)
async def list_my_families(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[Family]:
    """FAMILY-02: lista famílias onde o usuário autenticado é membro."""
    from caramello_api.families.services import list_my_families as svc

    return await svc(session, current_user)


# ---------------------------------------------------------------------------
# FAMILY-03: GET /families/families/{family_uuid}
# ---------------------------------------------------------------------------


@router.get("/families/{family_uuid}", response_model=FamilyRead)
async def get_family_detail(
    family_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Family:
    """FAMILY-03: retorna detalhes da família se o usuário é membro; 403 senão."""
    return await _require_member(family_uuid, current_user, session)


# ---------------------------------------------------------------------------
# D-07: POST /families/families/{family_uuid}/pre-register
# ---------------------------------------------------------------------------


@router.post(
    "/families/{family_uuid}/pre-register",
    response_model=FamilyInvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def pre_register_member(
    family_uuid: UUID,
    body: PreRegisterBody,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FamilyInvitation:
    """D-07: owner pré-registra um email para adesão automática (D-02 auto-join)."""
    family, _ = await _require_owner(family_uuid, current_user, session)

    invitation = FamilyInvitation(
        family_id=family.id,
        inviter_id=current_user.id,
        email=str(body.email),
        status="pending_login",
    )
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)
    return invitation


# ---------------------------------------------------------------------------
# D-07: GET /families/families/{family_uuid}/members
# ---------------------------------------------------------------------------


@router.get(
    "/families/{family_uuid}/members",
    response_model=list[FamilyMemberRead],
)
async def list_members(
    family_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[FamilyMemberRead]:
    """D-07: lista todos os membros se o requisitante é membro da família."""
    family = await _require_member(family_uuid, current_user, session)

    result = await session.exec(
        select(User, FamilyMember)
        .join(FamilyMember, FamilyMember.user_id == User.id)  # type: ignore[arg-type]
        .where(FamilyMember.family_id == family.id)
    )
    rows = list(result.all())
    return [
        FamilyMemberRead(
            user_uuid=user.uuid,
            role=member.role,
            joined_at=member.joined_at,
        )
        for user, member in rows
    ]


# ---------------------------------------------------------------------------
# FAMILY-07: DELETE /families/families/{family_uuid}/members/{user_uuid}
# ---------------------------------------------------------------------------


@router.delete(
    "/families/{family_uuid}/members/{user_uuid}",
    status_code=status.HTTP_200_OK,
)
async def remove_member(
    family_uuid: UUID,
    user_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    """FAMILY-07: owner remove membro da família; 403 caso contrário."""
    family, _ = await _require_owner(family_uuid, current_user, session)

    # Localizar o user-alvo
    target_result = await session.exec(select(User).where(User.uuid == user_uuid))
    target_user = target_result.first()
    if target_user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Localizar o membership
    member_result = await session.exec(
        select(FamilyMember).where(
            FamilyMember.family_id == family.id,
            FamilyMember.user_id == target_user.id,
        )
    )
    target_member = member_result.first()
    if target_member is None:
        raise HTTPException(status_code=404, detail="Usuário não é membro desta família")

    await session.delete(target_member)
    await session.commit()
    return {"ok": True}
