# CARAMELLO-GENERATED: implemented
from __future__ import annotations

from fastapi import APIRouter, Depends

from caramello_api.shared.auth import get_current_user
from caramello_api.users.models import User
from caramello_api.users.schemas import UserRead

router = APIRouter(prefix="/users", tags=["User"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Retorna o perfil do usuário autenticado."""
    return current_user
