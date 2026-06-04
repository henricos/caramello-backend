"""Serviços de domínio para families — lógica pura, sem dependências FastAPI.

Funções recebem AsyncSession e User como parâmetros diretos (não via Depends),
tornando-as reutilizáveis em contextos MCP, testes e outros callers sem framework.
"""

from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.families.models import Family, FamilyMember
from caramello.users.models import User


async def list_my_families(session: AsyncSession, user: User) -> list[Family]:
    """Retorna as famílias onde o usuário autenticado é membro.

    Filtra por FamilyMember.user_id == user.id — o chamador é responsável por
    garantir que user vem de uma fonte confiável (ex: get_current_user via JWT).
    Erros de domínio são erros Python puros; o caller (operations.py) trata e
    converte para respostas HTTP adequadas.
    """
    result = await session.exec(
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)  # type: ignore[arg-type]
        .where(FamilyMember.user_id == user.id)
    )
    return list(result.all())
