# CARAMELLO-GENERATED: stub
from __future__ import annotations

from fastapi import APIRouter, Depends

from caramello.shared.auth import get_current_user
from caramello.user.models import User, UserRead

router = APIRouter(prefix="/user", tags=["User"])

@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Retorna o perfil do usuário autenticado."""
    raise NotImplementedError

