"""Testes para shared/auth.py — AUTH-01, AUTH-02, AUTH-03.

Estratégia: para AUTH-01 (401 sem token) usamos TestClient diretamente.
Para AUTH-02/03 que dependem de banco real, usamos `@pytest.mark.integration`
e mocking via app.dependency_overrides (Phase 5 implementa banco isolado).
"""
from __future__ import annotations

import pytest


def test_auth_module():
    """AUTH-03: get_current_user é importável de caramello.shared.auth."""
    from caramello.shared.auth import (
        fetch_jwks,  # noqa: F401
        get_current_user,  # noqa: F401
    )


def test_me_unauthenticated(client):
    """AUTH-01: GET /users/me sem token retorna 401 (ou 403 do HTTPBearer)."""
    response = client.get("/users/me")
    # HTTPBearer retorna 403 por padrão; 401 também é aceitável se a app configurar
    assert response.status_code in (401, 403), (
        f"Esperado 401 ou 403 sem token; recebido {response.status_code}: {response.text}"  # noqa: E501
    )


def test_user_crud_requires_auth(client):
    """D-11 / AUTH-01: GET /users/user/ (CRUD) sem token retorna 401/403."""
    response = client.get("/users/user/")
    assert response.status_code in (401, 403)


@pytest.mark.integration
def test_jit_provisioning():
    """AUTH-02: primeira request com token válido cria registro na tabela users.

    Nota: este teste é marcado @pytest.mark.integration porque depende de banco
    real configurado via .env. Phase 5 entrega banco isolado (TEST-01).
    Até lá, este teste roda apenas em ambiente local com banco e Keycloak reais.
    """
    pytest.skip(
        "Requer Keycloak real e banco PostgreSQL configurado via .env "
        "(executado manualmente pelo operador no plano 03-07; "
        "banco isolado vem na Phase 5)"
    )


def test_jwt_decode_only_accepts_rs256():
    """Threat T-3-03: jwt.decode em shared/auth.py declara algorithms=['RS256']."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    auth_src = (repo_root / "src/caramello/shared/auth.py").read_text()
    assert 'algorithms=["RS256"]' in auth_src or "algorithms=['RS256']" in auth_src, (
        "shared/auth.py deve restringir algorithms=['RS256'] explicitamente"
    )
    assert '"none"' not in auth_src.lower().replace("'none'", '"none"'), (
        "shared/auth.py não deve aceitar algoritmo 'none'"
    )


def test_auto_join_on_login():
    """D-02: get_current_user faz auto-join se existir FamilyInvitation pendente.

    Skipa enquanto src/caramello/families/models.py não existir (plano 04-03).
    Quando existir, valida o comportamento via mock de session:
    - FamilyMember(role="member") é criado para a família do convite
    - invitation.status é marcado como "joined"
    """
    pytest.importorskip("caramello.families.models")
    from unittest.mock import AsyncMock, MagicMock, patch

    from caramello.families.models import FamilyInvitation, FamilyMember
    from caramello.shared import auth as auth_module

    # Construir uma FamilyInvitation pending_login simulada
    pending_inv = FamilyInvitation(
        id=1,
        family_id=99,
        inviter_id=1,
        email="recem@example.com",
        status="pending_login",
    )

    try:
        from caramello.users.models import User  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        from caramello.user.models import User  # type: ignore[no-redef]

    provisioned_user = User(
        id=50,
        idp_sub="kc-sub-recem",
        email="recem@example.com",
        name="Recem Cadastrado",
    )

    added = []
    # Sequência esperada de SELECTs em get_current_user (após plano 04-04):
    # 1) SELECT User WHERE idp_sub → retorna provisioned_user
    # 2) SELECT FamilyInvitation WHERE email==status=='pending_login' → pending_inv
    select_results = iter([provisioned_user, pending_inv])

    async def _exec(_stmt):
        r = MagicMock()
        try:
            r.first.return_value = next(select_results)
        except StopIteration:
            r.first.return_value = None
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock()
    # session.add() é SÍNCRONO em SQLAlchemy async — usar MagicMock para que
    # o side_effect seja executado imediatamente (sem await)
    mock_session.add = MagicMock(side_effect=lambda o: added.append(o))
    mock_session.commit = AsyncMock()

    # Mockar JWT decode + JWKS cache para evitar tocar Keycloak real
    fake_token_payload = {
        "sub": "kc-sub-recem",
        "email": "recem@example.com",
        "name": "Recem Cadastrado",
    }
    with (
        patch.object(auth_module, "_jwks_cache", {"fake-kid": object()}),
        patch.object(
            auth_module.jwt,
            "get_unverified_header",
            return_value={"kid": "fake-kid"},
        ),
        patch.object(
            auth_module.jwt,
            "decode",
            return_value=fake_token_payload,
        ),
    ):
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="fake.token.value"
        )

        import asyncio

        result_user = asyncio.run(
            auth_module.get_current_user(
                credentials=credentials,
                session=mock_session,
            )
        )

    # Asserções:
    # - User retornado deve ser o provisioned_user
    assert result_user.idp_sub == "kc-sub-recem"
    # - Um FamilyMember com role="member" foi adicionado para a família 99
    members = [o for o in added if isinstance(o, FamilyMember)]
    assert len(members) == 1, (
        f"Esperado 1 FamilyMember; foi {len(members)}: {added!r}"
    )
    assert members[0].role == "member"
    assert members[0].family_id == 99
    assert members[0].user_id == 50
    # - A invitation foi marcada como joined (mutação direta + add para persistir)
    assert pending_inv.status == "joined", (
        "FamilyInvitation.status deve ser 'joined' após auto-join; "
        f"foi {pending_inv.status!r}"
    )
