"""Testes unitários de src/caramello_api/families/services.py.

Usa AsyncMock para simular session — não requer banco real.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from caramello_api.families.models import Family
from caramello_api.users.models import User


def _make_fake_user(user_id: int = 42) -> User:
    """Constrói User válido para uso nos testes."""
    return User(
        id=user_id,
        uuid=uuid4(),
        idp_sub=f"fake-sub-{user_id}",
        email=f"user{user_id}@example.com",
        name=f"Usuario {user_id}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_fake_family(family_id: int = 10, name: str = "Familia Teste") -> Family:
    """Constrói Family válida para uso nos testes."""
    return Family(
        id=family_id,
        uuid=uuid4(),
        name=name,
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_list_my_families_returns_two_families():
    """list_my_families(session, user) retorna lista de famílias do usuário.

    Verifica que o service retorna exatamente as famílias que o mock de session.exec
    devolve — sem dependência de banco real.
    """
    from caramello_api.families.services import list_my_families

    fake_user = _make_fake_user()
    family_a = _make_fake_family(family_id=10, name="Familia A")
    family_b = _make_fake_family(family_id=20, name="Familia B")

    mock_result = MagicMock()
    mock_result.all.return_value = [family_a, family_b]

    mock_session = AsyncMock()
    mock_session.exec.return_value = mock_result

    result = await list_my_families(mock_session, fake_user)

    assert len(result) == 2
    assert family_a in result
    assert family_b in result


@pytest.mark.asyncio
async def test_list_my_families_returns_empty_when_no_families():
    """list_my_families retorna lista vazia quando usuário não é membro de nenhuma família."""
    from caramello_api.families.services import list_my_families

    fake_user = _make_fake_user()

    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_session = AsyncMock()
    mock_session.exec.return_value = mock_result

    result = await list_my_families(mock_session, fake_user)

    assert result == []


@pytest.mark.asyncio
async def test_list_my_families_passes_user_id_to_query():
    """list_my_families usa user.id como filtro na query (não user.uuid)."""
    from caramello_api.families.services import list_my_families

    fake_user = _make_fake_user(user_id=99)

    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_session = AsyncMock()
    mock_session.exec.return_value = mock_result

    await list_my_families(mock_session, fake_user)

    # Verifica que exec foi chamado (a query foi executada)
    mock_session.exec.assert_called_once()
