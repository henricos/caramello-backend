"""Testes para shared/auth.py — AUTH-01, AUTH-02, AUTH-03.

Estratégia: para AUTH-01 (401 sem token) usamos TestClient diretamente.
Para AUTH-02/03 que dependem de banco real, usamos `@pytest.mark.integration`
e mocking via app.dependency_overrides (Phase 5 implementa banco isolado).

Os testes das duas camadas de autorização (allowlist de e-mail e pertencimento
a família) chamam `get_current_user` diretamente com uma session mockada: o que
está sob teste é a ORDEM das verificações — em especial que nenhuma consulta ao
banco acontece antes de o token ser considerado confiável.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

CREDENTIALS = HTTPAuthorizationCredentials(scheme="Bearer", credentials="fake.token.value")


def _entity_results(*values):
    """Handler de `execute_mock` que responde `.scalars().first()` em sequência."""
    remaining = iter(values)

    def _handler(_stmt):
        result = MagicMock()
        try:
            result.first.return_value = next(remaining)
        except StopIteration:
            result.first.return_value = None
        return result

    return _handler


def _call_get_current_user(session, payload):
    """Executa `get_current_user` com o JWKS e o decode do JWT mockados."""
    from caramello_api.shared import auth as auth_module

    with (
        patch.object(auth_module, "_jwks_cache", {"fake-kid": object()}),
        patch.object(auth_module.jwt, "get_unverified_header", return_value={"kid": "fake-kid"}),
        patch.object(auth_module.jwt, "decode", return_value=payload),
    ):
        return asyncio.run(auth_module.get_current_user(credentials=CREDENTIALS, session=session))


def test_auth_module():
    """AUTH-03: get_current_user é importável de caramello.shared.auth."""
    from caramello_api.shared.auth import (
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
    auth_src = (repo_root / "src/caramello_api/shared/auth.py").read_text()
    assert 'algorithms=["RS256"]' in auth_src or "algorithms=['RS256']" in auth_src, (
        "shared/auth.py deve restringir algorithms=['RS256'] explicitamente"
    )
    assert '"none"' not in auth_src.lower().replace("'none'", '"none"'), (
        "shared/auth.py não deve aceitar algoritmo 'none'"
    )


def test_auto_join_on_login():
    """D-02: get_current_user faz auto-join se existir FamilyInvitation pendente.

    Skipa enquanto src/caramello_api/families/models.py não existir (plano 04-03).
    Quando existir, valida o comportamento via mock de session:
    - FamilyMember(role="member") é criado para a família do convite
    - invitation.status é marcado como "joined"
    """
    pytest.importorskip("caramello_api.families.models")

    from caramello_api.families.models import FamilyInvitation, FamilyMember
    from caramello_api.shared.models import AllowedEmail
    from tests.conftest import execute_mock

    # Construir uma FamilyInvitation pending_login simulada
    pending_inv = FamilyInvitation(
        id=1,
        family_id=99,
        inviter_id=1,
        email="recem@example.com",
        status="pending_login",
    )

    try:
        from caramello_api.users.models import User  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        from caramello_api.user.models import User  # type: ignore[no-redef]

    provisioned_user = User(
        id=50,
        idp_sub="kc-sub-recem",
        email="recem@example.com",
        name="Recem Cadastrado",
    )

    added = []
    # Sequência esperada de SELECTs em get_current_user:
    # 1) SELECT AllowedEmail WHERE email → allowlist libera o acesso
    # 2) SELECT User WHERE idp_sub → retorna provisioned_user
    # 3) SELECT FamilyInvitation WHERE email==status=='pending_login' → pending_inv
    _exec = _entity_results(
        AllowedEmail(id=1, email="recem@example.com"),
        provisioned_user,
        pending_inv,
    )

    mock_session = AsyncMock()
    # O INSERT ... ON CONFLICT DO NOTHING também passa por session.execute, mas
    # não lê nenhum accessor — logo não consome a sequência de _exec.
    mock_session.execute.side_effect = execute_mock(_exec)
    # session.add() é SÍNCRONO em SQLAlchemy async — usar MagicMock para que
    # o side_effect seja executado imediatamente (sem await)
    mock_session.add = MagicMock(side_effect=lambda o: added.append(o))
    mock_session.commit = AsyncMock()

    # Mockar JWT decode + JWKS cache para evitar tocar Keycloak real
    fake_token_payload = {
        "sub": "kc-sub-recem",
        "email": "recem@example.com",
        "email_verified": True,
        "name": "Recem Cadastrado",
    }
    result_user = _call_get_current_user(mock_session, fake_token_payload)

    # Asserções:
    # - User retornado deve ser o provisioned_user
    assert result_user.idp_sub == "kc-sub-recem"
    # - Um FamilyMember com role="member" foi adicionado para a família 99
    members = [o for o in added if isinstance(o, FamilyMember)]
    assert len(members) == 1, f"Esperado 1 FamilyMember; foi {len(members)}: {added!r}"
    assert members[0].role == "member"
    assert members[0].family_id == 99
    assert members[0].user_id == 50
    # - A invitation foi marcada como joined (mutação direta + add para persistir)
    assert pending_inv.status == "joined", (
        f"FamilyInvitation.status deve ser 'joined' após auto-join; foi {pending_inv.status!r}"
    )


# ----------------------------------------------------------------------
# Allowlist — a primeira camada de autorização
# ----------------------------------------------------------------------


def test_allowlist_helper_normalizes_the_email():
    """O helper consulta sempre o e-mail normalizado (strip + lowercase)."""
    from caramello_api.shared.auth import is_email_allowlisted
    from tests.conftest import execute_mock

    seen = []

    def _capture(stmt):
        seen.append(str(stmt.compile(compile_kwargs={"literal_binds": True})))
        result = MagicMock()
        result.first.return_value = None
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_capture)

    allowed = asyncio.run(is_email_allowlisted(mock_session, "  Pessoa@Exemplo.COM  "))

    assert allowed is False
    assert len(seen) == 1
    assert "pessoa@exemplo.com" in seen[0]
    assert "Pessoa@Exemplo.COM" not in seen[0]


def test_email_not_verified_is_rejected_before_any_db_access():
    """`email_verified` falsy → 403 antes de qualquer consulta ao banco."""
    mock_session = AsyncMock()

    payload = {
        "sub": "kc-sub-naoverificado",
        "email": "naoverificado@exemplo.com",
        "email_verified": False,
    }
    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(mock_session, payload)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["reason"] == "email_not_verified"
    # O ponto do teste: nenhuma query — sem custo e sem sinal de timing do
    # allowlist para um token cujo e-mail ainda não é confiável.
    mock_session.execute.assert_not_awaited()
    mock_session.execute.assert_not_called()
    # 403 nunca carrega WWW-Authenticate (a credencial foi entendida e negada).
    assert exc_info.value.headers is None


def test_missing_email_verified_claim_is_treated_as_false():
    """Claim ausente é negação, nunca default permissivo."""
    mock_session = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(
            mock_session,
            {"sub": "kc-sub-sem-claim", "email": "semclaim@exemplo.com"},
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["reason"] == "email_not_verified"
    mock_session.execute.assert_not_called()


def test_not_allowlisted_returns_403_without_leaking_the_address():
    """E-mail fora do allowlist → 403 not_allowlisted, sem eco do endereço."""
    from tests.conftest import execute_mock

    email = "forasteiro@exemplo.com"
    mock_session = AsyncMock()
    # Primeiro (e único) SELECT: o allowlist, que não encontra nada.
    mock_session.execute.side_effect = execute_mock(_entity_results(None))

    payload = {"sub": "kc-sub-forasteiro", "email": email, "email_verified": True}
    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(mock_session, payload)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["reason"] == "not_allowlisted"
    # O corpo do erro nunca revela o endereço consultado.
    assert email not in str(exc_info.value.detail)
    assert "forasteiro" not in str(exc_info.value.detail).lower()
    # Nenhum usuário é provisionado para quem não passou pelo allowlist:
    # o único execute foi o SELECT do allowlist.
    assert mock_session.execute.await_count == 1
    mock_session.commit.assert_not_called()


def test_email_claim_is_normalized_before_the_allowlist_lookup():
    """Claim com caixa alta é normalizado antes de comparar com o allowlist."""
    from tests.conftest import execute_mock

    seen = []

    def _capture(stmt):
        seen.append(str(stmt.compile(compile_kwargs={"literal_binds": True})))
        result = MagicMock()
        result.first.return_value = None
        return result

    mock_session = AsyncMock()
    mock_session.execute.side_effect = execute_mock(_capture)

    payload = {"sub": "kc-sub-caixa", "email": " Pessoa@Exemplo.COM ", "email_verified": True}
    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(mock_session, payload)

    assert exc_info.value.status_code == 403
    assert "pessoa@exemplo.com" in seen[0]


def test_non_string_email_claim_is_a_401():
    """Claim `email` com tipo inesperado → 401, nunca um 500."""
    mock_session = AsyncMock()

    payload = {"sub": "kc-sub-tipo", "email": ["lista", "de", "emails"], "email_verified": True}
    with pytest.raises(HTTPException) as exc_info:
        _call_get_current_user(mock_session, payload)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["reason"] == "invalid_token"
    mock_session.execute.assert_not_called()


def test_401_carries_the_www_authenticate_header(client):
    """RFC 6750: um 401 aponta o cliente para o metadata do recurso protegido."""
    response = client.get("/users/me")

    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["reason"] == "missing_token"
    assert body["detail"]["message"]
    header = response.headers["www-authenticate"]
    assert header.startswith("Bearer ")
    assert "resource_metadata=" in header
    assert "/.well-known/oauth-protected-resource" in header


def test_audience_and_issuer_are_validated():
    """D-02 fechada: o decode valida `aud` e `iss` contra as Settings."""
    from caramello_api.core.config import get_settings
    from caramello_api.shared import auth as auth_module

    settings = get_settings()
    captured = {}

    def _fake_decode(token, key, **kwargs):
        captured.update(kwargs)
        return {"sub": "kc-sub", "email": "x@exemplo.com", "email_verified": False}

    mock_session = AsyncMock()
    with (
        patch.object(auth_module, "_jwks_cache", {"fake-kid": object()}),
        patch.object(auth_module.jwt, "get_unverified_header", return_value={"kid": "fake-kid"}),
        patch.object(auth_module.jwt, "decode", _fake_decode),
        pytest.raises(HTTPException),
    ):
        asyncio.run(auth_module.get_current_user(credentials=CREDENTIALS, session=mock_session))

    assert captured["algorithms"] == ["RS256"]
    assert captured["audience"] == settings.auth_oidc_audience
    assert captured["issuer"] == settings.auth_oidc_issuer
    assert captured["options"]["verify_aud"] is True
    assert captured["options"]["verify_iss"] is True
    # Toda claim que o código lê é obrigatória: faltar uma é 401, não KeyError.
    for claim in ("exp", "iss", "aud", "sub", "email"):
        assert claim in captured["options"]["require"]
