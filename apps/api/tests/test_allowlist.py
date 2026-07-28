"""Infraestrutura do allowlist: tabela, seed idempotente e PUBLIC_URL.

A tabela `allowed_emails` é infraestrutura de autorização, não entidade de
negócio: não vem do DSL, não tem schema público e não tem rota. Estes testes
travam exatamente essas propriedades.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def test_allowed_email_table_shape():
    """Colunas mínimas e ausência deliberada de `uuid` (nunca é exposta)."""
    from caramello_api.shared.models import AllowedEmail

    table = AllowedEmail.__table__
    assert table.name == "allowed_emails"
    assert set(table.columns.keys()) == {"id", "email", "created_at"}
    assert "uuid" not in table.columns

    email = table.columns["email"]
    assert email.type.length == 320
    assert email.unique is True
    assert email.nullable is False
    # Default do servidor: as inserções são `text()` puro, fora do flush do ORM.
    assert table.columns["created_at"].server_default is not None
    assert table.columns["created_at"].type.timezone is True


def test_allowed_email_is_declared_outside_the_generated_modules():
    """O gerador do DSL reescreve `{domain}/models.py`; a tabela não pode morar lá."""
    from caramello_api.shared.models import AllowedEmail

    assert AllowedEmail.__module__ == "caramello_api.shared.models"


def test_allowed_email_is_visible_to_alembic():
    """`migrations/env.py` precisa ver a tabela em `Base.metadata`."""
    from caramello_api.shared.base import Base
    from caramello_api.shared.models import AllowedEmail  # noqa: F401

    assert "allowed_emails" in Base.metadata.tables


def test_the_migration_0005_creates_the_table_with_a_named_unique_constraint():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "src/caramello_api/migrations/versions/0005_allowed_emails.py"
    ).read_text()

    assert 'revision: str = "0005"' in source
    assert 'down_revision: str | Sequence[str] | None = "0004"' in source
    assert "uq_allowed_emails_email" in source
    assert 'op.drop_table("allowed_emails")' in source


@pytest.mark.asyncio
async def test_seed_default_reference_is_idempotent_and_normalizes():
    """O seed usa ON CONFLICT DO NOTHING e grava o e-mail normalizado."""
    from caramello_api.shared.seeds import DEFAULT_ALLOWED_EMAILS, seed_default_reference

    executed = []

    connection = AsyncMock()
    connection.execute = AsyncMock(side_effect=lambda stmt, params: executed.append((stmt, params)))

    begin_context = MagicMock()
    begin_context.__aenter__ = AsyncMock(return_value=connection)
    begin_context.__aexit__ = AsyncMock(return_value=False)
    engine = MagicMock()
    engine.begin = MagicMock(return_value=begin_context)

    await seed_default_reference(engine)

    assert len(executed) == len(DEFAULT_ALLOWED_EMAILS)
    statement, params = executed[0]
    sql = str(statement)
    assert "INSERT INTO allowed_emails" in sql
    assert "ON CONFLICT (email) DO NOTHING" in sql
    assert params["email"] == params["email"].strip().lower()
    assert "henricos@gmail.com" in [p["email"] for _, p in executed]


def test_public_url_defaults_outside_production():
    from caramello_api.core.config import Settings

    settings = Settings()  # type: ignore[call-arg]
    assert settings.public_url == "http://localhost:8000"


def test_public_url_is_required_in_production(monkeypatch):
    """Sem PUBLIC_URL o metadata de discovery anunciaria localhost — falha alto."""
    from pydantic import ValidationError

    from caramello_api.core.config import Settings

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("PUBLIC_URL", raising=False)

    with pytest.raises(ValidationError, match="PUBLIC_URL"):
        Settings()  # type: ignore[call-arg]


def test_public_url_loses_its_trailing_slash(monkeypatch):
    from caramello_api.core.config import Settings

    monkeypatch.setenv("PUBLIC_URL", "https://exemplo.com/caramello-api/")

    assert Settings().public_url == "https://exemplo.com/caramello-api"  # type: ignore[call-arg]
