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
    """AUTH-01: GET /user/me sem token retorna 401 (ou 403 do HTTPBearer)."""
    response = client.get("/user/me")
    # HTTPBearer retorna 403 por padrão; 401 também é aceitável se a app configurar
    assert response.status_code in (401, 403), (
        f"Esperado 401 ou 403 sem token; recebido {response.status_code}: {response.text}"  # noqa: E501
    )


def test_user_crud_requires_auth(client):
    """D-11 / AUTH-01: GET /user/ (CRUD) sem token retorna 401/403."""
    response = client.get("/user/")
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
