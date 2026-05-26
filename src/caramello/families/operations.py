# CARAMELLO-GENERATED: stub
from __future__ import annotations

from fastapi import APIRouter, Depends

from caramello.families.models import Family, FamilyRead
from caramello.shared.auth import get_current_user

router = APIRouter(prefix="/families", tags=["Family"])


@router.post("/registry", response_model=FamilyRead)
async def registry_family(current_user: Family = Depends(get_current_user)) -> Family:
    """Cria família e registra o usuário autenticado como owner (role='owner')."""
    raise NotImplementedError


@router.get("/families", response_model=FamilyRead)
async def list_my_families(current_user: Family = Depends(get_current_user)) -> Family:
    """Lista famílias das quais o usuário autenticado é membro."""
    raise NotImplementedError


@router.get("/families/{family_uuid}", response_model=FamilyRead)
async def get_family_detail(current_user: Family = Depends(get_current_user)) -> Family:
    """Retorna detalhes de uma família se o usuário for membro; 403 se não for."""
    raise NotImplementedError


@router.post("/families/{family_uuid}/pre-register", response_model=FamilyRead)
async def pre_register_member(
    current_user: Family = Depends(get_current_user),
) -> Family:
    """Owner pré-registra email para adesão automática. Não-owner recebe 403."""
    raise NotImplementedError


@router.get("/families/{family_uuid}/members", response_model=FamilyRead)
async def list_members(current_user: Family = Depends(get_current_user)) -> Family:
    """Lista membros da família (qualquer membro pode ver)."""
    raise NotImplementedError


@router.delete("/families/{family_uuid}/members/{user_uuid}", response_model=FamilyRead)
async def remove_member(current_user: Family = Depends(get_current_user)) -> Family:
    """Remove membro da família (owner only). Não-owner recebe 403."""
    raise NotImplementedError
