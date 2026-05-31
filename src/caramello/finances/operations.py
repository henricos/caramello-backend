# CARAMELLO-GENERATED: stub
from __future__ import annotations

from fastapi import APIRouter, Depends

from caramello.finances.models import Account, AccountRead
from caramello.shared.auth import get_current_user

router = APIRouter(prefix="/finances", tags=["Account"])


@router.get("/account", response_model=AccountRead)
async def list_accounts(current_user: Account = Depends(get_current_user)) -> Account:
    """Lista contas bancárias da família autenticada."""
    raise NotImplementedError
