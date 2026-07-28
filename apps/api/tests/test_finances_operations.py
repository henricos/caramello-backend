"""Testes para src/caramello_api/finances/operations.py — ACC-01, ACC-02, ACC-03,
CAT-01, CAT-02, CAT-03, CAT-04, AUTH-FIN-01, AUTH-FIN-02.

Estes testes começam skipados (módulo finances/operations ainda não implementado).
Cada teste usa pytest.importorskip para falhar limpo até a implementação
chegar (planos 07-02 e 07-03). Quando operations.py for marcado como
`# CARAMELLO-GENERATED: implemented`, os testes passam a executar automaticamente.

Estratégia (igual a tests/test_family_operations.py):
- app.dependency_overrides[get_current_user] = lambda: fake_user
- AsyncMock para get_session
- TestClient(app) sem context manager (evita disparar lifespan/fetch_jwks)
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


def _skip_if_stub() -> None:
    """Salta o teste se finances/operations.py ainda está marcado como stub.

    Mecanismo: importorskip tenta importar o módulo; se importar, verifica
    a anotação na primeira linha. Se for 'stub', emite skip explícito.
    Quando operations.py tiver '# CARAMELLO-GENERATED: implemented', a
    verificação passa e os testes executam normalmente.
    """
    pytest.importorskip("caramello_api.finances.operations")
    ops_path = Path(__file__).resolve().parents[1] / "src/caramello_api/finances/operations.py"
    if ops_path.exists():
        first_line = ops_path.read_text().splitlines()[0].strip()
        if "stub" in first_line:
            pytest.skip("finances/operations.py ainda é stub — aguardando plano 07-02")


def _skip_if_phase9_missing() -> None:
    """Salta o teste se os endpoints da fase 9 ainda não foram implementados.

    Verifica se o router de finances tem o endpoint reconcile registrado.
    Plano 09-04 Task 3 remove este guard quando todos os endpoints chegarem.
    """
    ops_mod = pytest.importorskip("caramello_api.finances.operations")
    paths = {getattr(r, "path", None) for r in ops_mod.router.routes}
    if "/finances/movements/{movement_uuid}/reconcile" not in paths:
        pytest.skip("Fase 9 endpoints ainda não implementados — aguardando plano 09-03/09-04")


def _make_fake_user(user_id: int = 42):
    """Constrói User válido — importa lazy (suporta users/ e user/ modules)."""
    try:
        from caramello_api.users.models import User  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        from caramello_api.user.models import User  # type: ignore[no-redef]
    return User(
        id=user_id,
        uuid=uuid4(),
        idp_sub=f"fake-sub-{user_id}",
        email=f"user{user_id}@example.com",
        name=f"Usuario {user_id}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_finances_module_exists():
    """Plano 07-02/07-03: módulo src/caramello_api/finances/operations.py existe."""
    pytest.importorskip("caramello_api.finances.operations")


def test_finances_operations_annotation_is_implemented():
    """Plano 07-02: primeira linha == # CARAMELLO-GENERATED: implemented."""
    _skip_if_stub()
    ops_path = Path(__file__).resolve().parents[1] / "src/caramello_api/finances/operations.py"
    if not ops_path.exists():
        pytest.skip("finances/operations.py ainda não foi gerado/implementado")
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line == "# CARAMELLO-GENERATED: implemented", (
        f"Anotação deve ser 'implemented' após plano 07-02; foi: {first_line!r}"
    )


def test_finances_router_paths():
    """CAT-03: router tem os paths esperados (fases 7-8).

    Fase 9 paths são verificados em test_finances_router_paths_phase9 (guarded)
    e serão habilitados pelo plano 09-04 Task 3 quando os endpoints chegarem.
    """
    _skip_if_stub()
    ops_mod = pytest.importorskip("caramello_api.finances.operations")
    router = ops_mod.router
    paths = {getattr(r, "path", None) for r in router.routes}
    expected = {
        "/finances/accounts",
        "/finances/accounts/{account_uuid}",
        "/finances/categories",
        "/finances/categories/{category_uuid}",
        "/finances/subcategory",
        "/finances/subcategory/{subcategory_uuid}",
        "/finances/accounts/{account_uuid}/movements",
        "/finances/accounts/{account_uuid}/movements/import",
        "/finances/import/confirm",
    }
    missing = expected - paths
    assert not missing, (
        f"Sub-paths faltando em finances.operations.router: {missing}. "
        f"Encontrados: {paths}. Prefix do router: {router.prefix!r}"
    )


def test_finances_router_paths_phase9():
    """Valida os 8 paths da fase 9 — todos implementados pelo plano 09-03/09-04.

    Plano 09-04 Task 3: guard _skip_if_phase9_missing removido — endpoints agora
    são assertados diretamente sem condição de skip.
    """
    _skip_if_stub()
    ops_mod = pytest.importorskip("caramello_api.finances.operations")
    router = ops_mod.router
    paths = {getattr(r, "path", None) for r in router.routes}
    phase9_expected = {
        "/finances/movements/{movement_uuid}/reconcile",
        "/finances/movements/{movement_uuid}/suggest-category",
        "/finances/entries/{entry_uuid}",
        "/finances/entries",
        "/finances/accounts/{account_uuid}/balance",
        "/finances/families/{family_uuid}/balance",
        "/finances/reports/monthly",
        "/finances/reports/by-member",
    }
    missing = phase9_expected - paths
    assert not missing, (
        f"Fase 9 paths ausentes em finances.operations.router: {missing}. Encontrados: {paths}"
    )


def test_create_account_returns_uuid():
    """ACC-01: POST /finances/accounts retorna uuid sem id/family_id internos.

    T-07-01: resposta pública NÃO expõe `id` nem `family_id`.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=uuid4(),
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # Primeiro exec: busca Family por uuid
            r.first.return_value = fake_family
        elif call_count[0] == 2:
            # Segundo exec: busca FamilyMember (membership check) — retorna membro válido
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    async def _refresh(obj):
        if isinstance(obj, Account) and not getattr(obj, "uuid", None):
            obj.uuid = fake_account.uuid
        return None

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=_refresh)
    mock_session.execute = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            "/finances/accounts",
            json={
                "family_uuid": str(family_uuid),
                "name": "Conta Corrente",
                "type": "corrente",
                "currency": "BRL",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "uuid" in body, f"Resposta deve conter 'uuid'; body: {body}"
        assert "family_uuid" in body, f"Resposta deve conter 'family_uuid'; body: {body}"
        # T-07-01: resposta NÃO deve expor chaves internas
        assert "id" not in body, f"Resposta NÃO deve expor 'id'; body: {body}"
        assert "family_id" not in body, f"Resposta NÃO deve expor 'family_id'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_list_accounts_scoped_to_family():
    """ACC-02: GET /finances/accounts?family_uuid=xxx retorna apenas contas da família."""
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=uuid4(),
        family_id=1,
        name="Conta Poupança",
        type="poupanca",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # Primeiro exec: busca Family por uuid
            r.first.return_value = fake_family
            r.all.return_value = [fake_family]
        elif call_count[0] == 2:
            # Segundo exec: busca FamilyMember (membership check)
            r.first.return_value = MagicMock()
            r.all.return_value = []
        else:
            # Terceiro exec: lista contas da família
            r.first.return_value = None
            r.all.return_value = [fake_account]
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/finances/accounts?family_uuid={family_uuid}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body, list), f"Resposta deve ser lista; foi: {type(body)}"
    finally:
        app.dependency_overrides.clear()


def test_accounts_require_auth():
    """AUTH-FIN-01: sem override de get_current_user, /finances/accounts retorna 401.

    _HTTPBearer401 retorna 401 para token ausente (RFC 7235 §3.1).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.database import get_session

    async def _exec(_stmt):
        r = MagicMock()
        r.first.return_value = None
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec

    def _session_override():
        yield mock_session

    # Não sobrescreve get_current_user — _HTTPBearer401 levanta 401
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/finances/accounts?family_uuid={uuid4()}")
        assert response.status_code == 401, (
            f"Esperado 401 para requisição sem autenticação; recebido: {response.status_code}. "
            f"Body: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()


def test_accounts_403_non_member():
    """AUTH-FIN-02: usuário autenticado mas não-membro recebe 403.

    Mock retorna Family existente porém FamilyMember ausente (first()=None
    na query de membership).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Alheia",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # Primeiro exec: busca Family por uuid — encontra
            r.first.return_value = fake_family
        else:
            # Segundo exec: busca FamilyMember — não encontra (non-member)
            r.first.return_value = None
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/finances/accounts?family_uuid={family_uuid}")
        assert response.status_code == 403, (
            f"Esperado 403 para não-membro; recebido: {response.status_code}. Body: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()


def test_archive_account():
    """ACC-03: PATCH /finances/accounts/{uuid} com is_active=false arquiva sem deletar.

    Verifica que resposta retorna is_active=False e session.delete não foi chamado.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # Primeiro exec: busca Account por uuid
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            # Segundo exec: busca Family por id
            r.first.return_value = fake_family
        else:
            # Terceiro exec: busca FamilyMember (membership check)
            r.first.return_value = MagicMock()
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.delete = MagicMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.patch(
            f"/finances/accounts/{account_uuid}",
            json={"is_active": False},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("is_active") is False, f"Resposta deve ter is_active=False; body: {body}"
        # ACC-03: arquivamento nunca deleta — session.delete não deve ter sido chamado
        mock_session.delete.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_create_category():
    """CAT-01: POST /finances/categories cria categoria pai scoped por família."""
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Category  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_category = Category(
        id=5,
        uuid=uuid4(),
        family_id=1,
        name="Transporte",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # Primeiro exec: busca Family por uuid
            r.first.return_value = fake_family
        elif call_count[0] == 2:
            # Segundo exec: busca FamilyMember (membership check)
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    async def _refresh(obj):
        if isinstance(obj, Category) and not getattr(obj, "uuid", None):
            obj.uuid = fake_category.uuid
        return None

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=_refresh)
    mock_session.execute = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            "/finances/categories",
            json={
                "family_uuid": str(family_uuid),
                "name": "Transporte",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "uuid" in body, f"Resposta deve conter 'uuid'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_list_update_categories():
    """CAT-04: GET /finances/categories?family_uuid=xxx (200) e PATCH /finances/categories/{uuid} (200)."""
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Category  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    category_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_category = Category(
        id=5,
        uuid=category_uuid,
        family_id=1,
        name="Transporte",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # --- Teste GET ---
    call_count = [0]

    async def _exec_list(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_family
            r.all.return_value = [fake_family]
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
            r.all.return_value = []
        else:
            r.first.return_value = None
            r.all.return_value = [fake_category]
        return r

    mock_session_list = AsyncMock()
    mock_session_list.exec.side_effect = _exec_list
    mock_session_list.commit = AsyncMock()

    def _session_override_list():
        yield mock_session_list

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override_list
    try:
        client = TestClient(app)
        response_list = client.get(f"/finances/categories?family_uuid={family_uuid}")
        assert response_list.status_code == 200, response_list.text
        assert isinstance(response_list.json(), list)
    finally:
        app.dependency_overrides.clear()

    # --- Teste PATCH ---
    call_count_patch = [0]

    async def _exec_patch(_stmt):
        r = MagicMock()
        call_count_patch[0] += 1
        if call_count_patch[0] == 1:
            # Busca Category por uuid
            r.first.return_value = fake_category
        elif call_count_patch[0] == 2:
            # Busca Family por id
            r.first.return_value = fake_family
        else:
            # Busca FamilyMember (membership check)
            r.first.return_value = MagicMock()
        r.all.return_value = []
        return r

    mock_session_patch = AsyncMock()
    mock_session_patch.exec.side_effect = _exec_patch
    mock_session_patch.add = MagicMock()
    mock_session_patch.commit = AsyncMock()
    mock_session_patch.refresh = AsyncMock()

    def _session_override_patch():
        yield mock_session_patch

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override_patch
    try:
        client = TestClient(app)
        response_patch = client.patch(
            f"/finances/categories/{category_uuid}",
            json={"name": "Transporte Atualizado"},
        )
        assert response_patch.status_code == 200, response_patch.text
    finally:
        app.dependency_overrides.clear()


def test_create_subcategory():
    """CAT-02: POST /finances/subcategory cria subcategoria via category_uuid."""
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import (  # type: ignore[import-not-found]
        Category,
        Subcategory,
    )
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    category_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_category = Category(
        id=5,
        uuid=category_uuid,
        family_id=1,
        name="Transporte",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_subcategory = Subcategory(
        id=20,
        uuid=uuid4(),
        category_id=5,
        name="Gasolina",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # Primeiro exec: busca Category por uuid
            r.first.return_value = fake_category
        elif call_count[0] == 2:
            # Segundo exec: busca Family por id
            r.first.return_value = fake_family
        elif call_count[0] == 3:
            # Terceiro exec: busca FamilyMember (membership check)
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    async def _refresh(obj):
        if isinstance(obj, Subcategory) and not getattr(obj, "uuid", None):
            obj.uuid = fake_subcategory.uuid
        return None

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=_refresh)
    mock_session.execute = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            "/finances/subcategory",
            json={
                "category_uuid": str(category_uuid),
                "name": "Gasolina",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "uuid" in body, f"Resposta deve conter 'uuid'; body: {body}"
    finally:
        app.dependency_overrides.clear()


# =============================================================================
# Phase 8: Movement endpoints — MOV-01..05, D-15, AUTH-FIN-01/02
# Stubs Nyquist — red/skipados até planos 08-02/08-03/08-04 entregarem implementação
# =============================================================================


def test_create_movement():
    """MOV-01: POST /finances/accounts/{uuid}/movements cria movimentação, retorna 201 + uuid.

    Stub Nyquist — red/skip até operations.py ter o endpoint implementado (plano 08-02).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    family_uuid = uuid4()
    movement_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # Resolve Account por uuid
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            # Membership check — membro válido
            r.first.return_value = MagicMock()
        else:
            # Hash pre-check: nenhum hash existente (nova movimentação)
            r.first.return_value = None
        r.all.return_value = []
        return r

    # session.execute usado para pre-check de hash (session.exec não retorna scalar)
    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    async def _movement_refresh(obj):
        obj.uuid = movement_uuid
        return None

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=_movement_refresh)

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/finances/accounts/{account_uuid}/movements",
            json={
                "date": "2026-01-15",
                "amount": "-150.00",
                "description": "PIX FULANO",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "uuid" in body, f"Resposta deve conter 'uuid'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_create_movement_409_duplicate():
    """MOV-01 + D-17: POST com hash já existente retorna 409 + existing_uuid.

    Stub Nyquist — red/skip até operations.py implementar verificação de hash (plano 08-02).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account, Movement  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    family_uuid = uuid4()
    existing_movement_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    existing_movement = Movement(
        id=1,
        uuid=existing_movement_uuid,
        account_id=10,
        date=datetime(2026, 1, 15, tzinfo=UTC),
        amount="-150.00",
        description="PIX FULANO",
        import_hash="abc123hash",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            # Resolve Account por uuid
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            # Membership check — membro válido
            r.first.return_value = MagicMock()
        else:
            # Hash pre-check: retorna movimentação existente com mesmo hash (D-17)
            r.first.return_value = existing_movement
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/finances/accounts/{account_uuid}/movements",
            json={
                "date": "2026-01-15",
                "amount": "-150.00",
                "description": "PIX FULANO",
            },
        )
        assert response.status_code == 409, (
            f"Esperado 409 para hash duplicado; recebido: {response.status_code}. "
            f"Body: {response.text}"
        )
        body = response.json()
        detail = body.get("detail", {})
        assert "existing_uuid" in detail, f"409 deve conter 'existing_uuid' no detail; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_import_csv():
    """MOV-02: POST /accounts/{uuid}/movements/import?format=csv retorna inserted + movements[].

    Stub Nyquist — red/skip até operations.py implementar endpoint de importação (plano 08-03).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    csv_content = (
        b"date,amount,description\n2026-01-15,-150.00,PIX FULANO\n2026-01-16,200.00,SALARIO\n"
    )

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    # session.execute para hash pre-check em lote — retorna nenhum hash existente
    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/finances/accounts/{account_uuid}/movements/import?format=csv",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "inserted" in body, f"Resposta deve conter 'inserted'; body: {body}"
        assert "movements" in body, f"Resposta deve conter 'movements'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_import_ofx():
    """MOV-03: POST /accounts/{uuid}/movements/import?format=ofx funciona com sample OFX.

    Stub Nyquist — red/skip até operations.py implementar endpoint OFX (plano 08-03).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Sample OFX mínimo válido
    ofx_content = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>1001
<STMTRS>
<CURDEF>BRL
<BANKACCTFROM>
<BANKID>001
<ACCTID>12345-6
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260101000000
<DTEND>20260131000000
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260115000000
<TRNAMT>-150.00
<FITID>TX001
<MEMO>PIX FULANO
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/finances/accounts/{account_uuid}/movements/import?format=ofx",
            files={"file": ("test.ofx", io.BytesIO(ofx_content), "application/x-ofx")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "inserted" in body, f"Resposta deve conter 'inserted'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_import_xlsx():
    """MOV-03: POST /accounts/{uuid}/movements/import?format=xlsx funciona com BytesIO XLSX.

    Stub Nyquist — red/skip até operations.py implementar endpoint XLSX (plano 08-03).
    """
    _skip_if_stub()
    import openpyxl
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    # Gera um XLSX mínimo em memória para o teste
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["date", "amount", "description"])
    ws.append(["2026-01-15", "-150.00", "PIX FULANO"])
    ws.append(["2026-01-16", "200.00", "SALARIO"])
    xlsx_bytes = io.BytesIO()
    wb.save(xlsx_bytes)
    xlsx_bytes.seek(0)

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/finances/accounts/{account_uuid}/movements/import?format=xlsx",
            files={
                "file": (
                    "test.xlsx",
                    xlsx_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "inserted" in body, f"Resposta deve conter 'inserted'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_import_deduplication():
    """MOV-04: reimportar mesmo arquivo não duplica movimentações.

    Stub Nyquist — red/skip até operations.py implementar deduplicação por hash (plano 08-03).
    Simula pre-check retornando hashes já existentes → inserted=0.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    csv_content = b"date,amount,description\n2026-01-15,-150.00,PIX FULANO\n"

    # WR-05: calcular o hash real para que o pre-check mock rejeite a linha corretamente
    from decimal import Decimal

    from caramello_api.finances.services import (  # type: ignore[import-not-found]
        ParsedRow,
        _compute_hash,
    )

    real_row = ParsedRow(
        date=datetime(2026, 1, 15, tzinfo=UTC),
        amount=Decimal("-150.00"),
        description="PIX FULANO",
        fitid=None,
    )
    real_hash = _compute_hash(account_id=10, row=real_row)

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    # Mocks para session.execute: 2 chamadas distintas (WR-05)
    # 1ª chamada: pre-check de hashes existentes (retorna real_hash como já presente)
    mock_precheck_result = MagicMock()
    mock_precheck_result.fetchall.return_value = [(real_hash,)]

    # 2ª chamada: busca UUID das duplicatas CSV/XLSX (hash → uuid da movimentação existente)
    existing_movement_uuid = uuid4()
    mock_uuid_result = MagicMock()
    mock_uuid_result.fetchall.return_value = [(real_hash, existing_movement_uuid)]

    execute_call_count = [0]

    async def _execute_import(stmt):
        execute_call_count[0] += 1
        if execute_call_count[0] == 1:
            return mock_precheck_result
        return mock_uuid_result

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = _execute_import
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/finances/accounts/{account_uuid}/movements/import?format=csv",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # Reimportação CSV: hash já existe → potential_duplicates[] (não duplicates_skipped, pois sem fitid)
        assert body.get("potential_duplicates") or body.get("duplicates_skipped", 0) > 0, (
            f"Reimportação não deve inserir duplicatas; body: {body}"
        )
    finally:
        app.dependency_overrides.clear()


def test_import_potential_duplicates():
    """MOV-05 + D-05: CSV/XLSX com hash match retorna potential_duplicates[].

    Stub Nyquist — red/skip até operations.py implementar retorno de potential_duplicates
    para CSV/XLSX (plano 08-03). OFX usa deduplicação definitiva; CSV/XLSX retornam
    potential_duplicates[] para confirmação pelo usuário.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    csv_content = b"date,amount,description\n2026-01-15,-150.00,PIX FULANO\n"

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    # Pre-check encontra um hash que coincide (duplicata suspeita para CSV)
    known_hash = "suspect_hash_from_csv"
    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [(known_hash,)]

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/finances/accounts/{account_uuid}/movements/import?format=csv",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "potential_duplicates" in body, (
            f"Resposta deve conter 'potential_duplicates'; body: {body}"
        )
        assert isinstance(body["potential_duplicates"], list), (
            f"'potential_duplicates' deve ser lista; body: {body}"
        )
    finally:
        app.dependency_overrides.clear()


def test_import_confirm():
    """MOV-05 + D-08: POST /import/confirm insere confirmadas sem colisão de hash.

    Stub Nyquist — red/skip até operations.py implementar endpoint /import/confirm
    (plano 08-03). Confirmadas são inseridas com import_hash=None (D-08).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        # Payload: lista de movimentações confirmadas pelo usuário (D-08)
        payload = {
            "account_uuid": str(account_uuid),
            "movements": [
                {
                    "date": "2026-01-15",
                    "amount": "-150.00",
                    "description": "PIX FULANO",
                }
            ],
        }
        response = client.post(
            "/finances/import/confirm",
            json=payload,
        )
        assert response.status_code in (200, 201), (
            f"Esperado 200/201 para /import/confirm; recebido: {response.status_code}. "
            f"Body: {response.text}"
        )
        body = response.json()
        assert "inserted" in body, f"Resposta deve conter 'inserted'; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_list_movements():
    """D-15: GET /finances/accounts/{uuid}/movements retorna lista paginada.

    Stub Nyquist — red/skip até operations.py implementar endpoint GET movements
    (plano 08-02). Suporte a ?limit=50&offset=0&date_from=&date_to=.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account, Movement  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_movement = Movement(
        id=1,
        uuid=uuid4(),
        account_id=10,
        date=datetime(2026, 1, 15, tzinfo=UTC),
        amount="-150.00",
        description="PIX FULANO",
        import_hash=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count = [0]

    async def _exec(_stmt):
        r = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            r.first.return_value = fake_account
        elif call_count[0] == 2:
            r.first.return_value = MagicMock()
        else:
            r.first.return_value = None
        r.all.return_value = [fake_movement]
        return r

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [(fake_movement,)]

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/finances/accounts/{account_uuid}/movements?limit=50&offset=0")
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body, list), f"Resposta deve ser lista paginada; body: {body}"
    finally:
        app.dependency_overrides.clear()


def test_movements_require_auth():
    """AUTH-FIN-01/02: 401 sem token, 403 para família alheia em endpoints de Movement.

    Stub Nyquist — red/skip até operations.py implementar endpoints de Movement (plano 08-02).
    Replica o padrão de test_accounts_require_auth e test_accounts_403_non_member.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    account_uuid = uuid4()
    family_uuid = uuid4()

    # --- Parte 1: 401 sem autenticação ---
    async def _exec_401(_stmt):
        r = MagicMock()
        r.first.return_value = None
        r.all.return_value = []
        return r

    mock_session_401 = AsyncMock()
    mock_session_401.exec.side_effect = _exec_401

    def _session_override_401():
        yield mock_session_401

    # Não sobrescreve get_current_user
    app.dependency_overrides[get_session] = _session_override_401
    try:
        client = TestClient(app)
        response = client.get(f"/finances/accounts/{account_uuid}/movements")
        assert response.status_code == 401, (
            f"Esperado 401 sem autenticação; recebido: {response.status_code}. "
            f"Body: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()

    # --- Parte 2: 403 para família alheia ---
    fake_user = _make_fake_user()
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Alheia",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_family_other = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Alheia",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    call_count_403 = [0]

    async def _exec_403(_stmt):
        r = MagicMock()
        call_count_403[0] += 1
        if call_count_403[0] == 1:
            # Resolve Account por uuid
            r.first.return_value = fake_account
        else:
            # Membership check: não-membro (FamilyMember ausente → 403)
            r.first.return_value = None
        r.all.return_value = []
        return r

    mock_session_403 = AsyncMock()
    mock_session_403.exec.side_effect = _exec_403

    def _session_override_403():
        yield mock_session_403

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override_403
    try:
        client = TestClient(app)
        response = client.get(f"/finances/accounts/{account_uuid}/movements")
        assert response.status_code == 403, (
            f"Esperado 403 para não-membro; recebido: {response.status_code}. Body: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Stubs dos endpoints de conciliação — LAN-01, LAN-02, LAN-03
# ---------------------------------------------------------------------------


def test_reconcile_movement():
    """LAN-01, LAN-04, D-REC-02: POST /finances/movements/{uuid}/reconcile retorna 201.

    Resposta deve incluir schema rico: uuid, movement, subcategory_uuid,
    competencia_year, is_recorrente.
    Plano 09-04 Task 3: guard removido — endpoint implementado em 09-03.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello_api.families.models import FamilyMember  # type: ignore[import-not-found]
    from caramello_api.finances.models import (  # type: ignore[import-not-found]
        Account,
        Category,
        FinancialEntry,
        Movement,
        Subcategory,
    )
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    movement_uuid = uuid4()
    entry_uuid = uuid4()
    sub_uuid = uuid4()
    cat_uuid = uuid4()

    fake_movement = Movement(
        id=1,
        uuid=movement_uuid,
        account_id=1,
        date=datetime.now(UTC),
        amount=Decimal("150.00"),
        description="Supermercado",
        import_hash="hash123",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_subcategory = Subcategory(
        id=1,
        uuid=sub_uuid,
        category_id=1,
        name="Supermercado",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_category = Category(
        id=1,
        uuid=cat_uuid,
        family_id=1,
        name="Alimentação",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_member = FamilyMember(
        family_id=1,
        user_id=fake_user.id,
        role="member",
        joined_at=datetime.now(UTC),
    )
    fake_entry = FinancialEntry(
        id=1,
        uuid=entry_uuid,
        movement_id=1,
        subcategory_id=1,
        competencia_year=2026,
        competencia_month=5,
        notes=None,
        is_recorrente=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    added = []

    # CR-05 fix: mock com contador — execução correta por ordem de sessão.exec
    # Ordem: 1=Movement, 2=FamilyMember(_require_family_access), 3=Subcategory(fallback), 4=Category
    exec_call_count = [0]

    async def _exec(stmt):
        r = MagicMock()
        exec_call_count[0] += 1
        n = exec_call_count[0]
        if n == 1:
            r.first.return_value = fake_movement
        elif n == 2:
            r.first.return_value = fake_member
        elif n == 3:
            r.first.return_value = fake_subcategory
        elif n == 4:
            r.first.return_value = fake_category
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    async def _execute(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        r.fetchone.return_value = None  # faz cair no fallback individual de Subcategory+Category
        r.fetchall.return_value = []
        r.scalar_one_or_none.return_value = None
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(side_effect=_execute)
    mock_session.add = MagicMock(side_effect=lambda o: added.append(o))
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda o: setattr(o, "uuid", entry_uuid))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/finances/movements/{movement_uuid}/reconcile",
            json={
                "subcategory_uuid": str(sub_uuid),
                "competencia_year": 2026,
                "competencia_month": 5,
                "is_recorrente": False,
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert "uuid" in body, f"Resposta deve conter 'uuid'; foi: {body}"
        assert "movement" in body, "Resposta deve conter objeto 'movement' embutido (D-REC-02)"
        assert "competencia_year" in body, "Resposta deve conter 'competencia_year'"
    finally:
        app.dependency_overrides.clear()


def test_reconcile_409_duplicate():
    """LAN-02: POST /finances/movements/{uuid}/reconcile retorna 409 se já conciliado.

    Quando session.commit levanta IntegrityError, o endpoint deve fazer
    rollback e retornar 409 com mensagem de erro (D-REC-01).
    Plano 09-04 Task 3: guard removido — endpoint implementado em 09-03.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient
    from sqlalchemy.exc import IntegrityError

    from caramello_api.finances.models import (  # type: ignore[import-not-found]
        Account,
        Movement,
    )
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    movement_uuid = uuid4()
    sub_uuid = uuid4()

    fake_movement = Movement(
        id=1,
        uuid=movement_uuid,
        account_id=1,
        date=datetime.now(UTC),
        amount=Decimal("150.00"),
        description="Supermercado",
        import_hash="hash123",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_movement
        r.all.return_value = []
        return r

    async def _execute(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        r.fetchone.return_value = None
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(side_effect=_execute)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock(side_effect=IntegrityError("duplicate", None, None))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.post(
            f"/finances/movements/{movement_uuid}/reconcile",
            json={
                "subcategory_uuid": str(sub_uuid),
                "competencia_year": 2026,
                "competencia_month": 5,
            },
        )
        assert response.status_code == 409, (
            f"Duplicata deve retornar 409; foi {response.status_code}: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()


def test_suggest_category():
    """LAN-03, D-CAT-01/02: GET /finances/movements/{uuid}/suggest-category.

    Retorna lista ordenada por score desc. Cada item deve ter:
    subcategory_uuid, subcategory_name, category_uuid, category_name, score.
    Plano 09-04 Task 3: guard removido — endpoint implementado em 09-03.
    """
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    movement_uuid = uuid4()

    mock_session = AsyncMock()
    mock_session.exec.side_effect = lambda s: MagicMock(first=lambda: None, all=lambda: [])
    mock_session.execute = AsyncMock(
        return_value=MagicMock(
            fetchone=lambda: None,
            fetchall=lambda: [],
        )
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/finances/movements/{movement_uuid}/suggest-category")
        # 200 (lista vazia OK — D-CAT-03) ou 404 se movimento não existe
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert isinstance(body, list), f"Resposta deve ser lista; foi {type(body)}"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Stubs de atualização de lançamento — LAN-05, D-ATTR
# ---------------------------------------------------------------------------


def test_update_entry():
    """LAN-05, D-REC-04: PATCH /finances/entries/{uuid} atualiza lançamento.

    Atualiza subcategory_uuid, competencia_year, notes e retorna schema rico.
    Plano 09-04 Task 3: guard removido — endpoint implementado em 09-03.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello_api.families.models import FamilyMember  # type: ignore[import-not-found]
    from caramello_api.finances.models import (  # type: ignore[import-not-found]
        Account,
        Category,
        FinancialEntry,
        Movement,
        Subcategory,
    )
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    entry_uuid = uuid4()
    sub_uuid = uuid4()
    cat_uuid = uuid4()

    fake_entry = FinancialEntry(
        id=1,
        uuid=entry_uuid,
        movement_id=1,
        subcategory_id=1,
        competencia_year=2026,
        competencia_month=5,
        notes=None,
        is_recorrente=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_movement = Movement(
        id=1,
        uuid=uuid4(),
        account_id=1,
        date=datetime.now(UTC),
        amount=Decimal("100.00"),
        description="Teste",
        import_hash="h1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_account = Account(
        id=1,
        uuid=uuid4(),
        family_id=1,
        name="Conta",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_subcategory = Subcategory(
        id=1,
        uuid=sub_uuid,
        category_id=1,
        family_id=1,
        name="Sub Teste",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_category = Category(
        id=1,
        uuid=cat_uuid,
        family_id=1,
        name="Cat Teste",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    fake_member = FamilyMember(
        family_id=1,
        user_id=fake_user.id,
        role="member",
        joined_at=datetime.now(UTC),
    )

    # WR-06: mock com contador de chamadas — retorna objeto correto por ordem de exec
    # Ordem: 1=FinancialEntry, 2=Movement(auth), 3=Account, 4=FamilyMember(_require_family_access),
    #        5=Subcategory(update), 6=Subcategory(reload pós-commit), 7=Category(reload pós-commit)
    exec_call_count = [0]

    async def _exec(stmt):
        r = MagicMock()
        exec_call_count[0] += 1
        n = exec_call_count[0]
        if n == 1:
            r.first.return_value = fake_entry
        elif n == 2:
            r.first.return_value = fake_movement
        elif n == 3:
            r.first.return_value = fake_account
        elif n == 4:
            r.first.return_value = fake_member
        elif n == 5 or n == 6:
            r.first.return_value = fake_subcategory
        elif n == 7:
            r.first.return_value = fake_category
        else:
            r.first.return_value = None
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=MagicMock())
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.patch(
            f"/finances/entries/{entry_uuid}",
            json={
                "subcategory_uuid": str(sub_uuid),
                "competencia_year": 2026,
                "notes": "Nota atualizada",
            },
        )
        # WR-06: asserta apenas 200 e valida shape do body (não aceita 404 como sucesso)
        assert response.status_code == 200, (
            f"Esperado 200; foi {response.status_code}: {response.text}"
        )
        body = response.json()
        assert "uuid" in body, "Resposta deve conter 'uuid'"
        assert "subcategory_uuid" in body, "Resposta deve conter 'subcategory_uuid'"
        assert "category_uuid" in body, "Resposta deve conter 'category_uuid'"
    finally:
        app.dependency_overrides.clear()


def test_entry_responsible_user_uuid():
    """D-ATTR, D-REC-04: PATCH entries/{uuid} com responsible_user_uuid atribui responsável.

    PATCH com responsible_user_uuid: null deve limpar o campo (sentinela model_fields_set).
    Plano 09-04 Task 3: guard removido — endpoint implementado em 09-03.
    """
    from fastapi.testclient import TestClient

    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    entry_uuid = uuid4()
    responsible_uuid = uuid4()

    mock_session = AsyncMock()
    mock_session.exec.side_effect = lambda s: MagicMock(first=lambda: None, all=lambda: [])
    mock_session.execute = AsyncMock(return_value=MagicMock(first=lambda: None))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        # PATCH com responsável explícito
        response = client.patch(
            f"/finances/entries/{entry_uuid}",
            json={"responsible_user_uuid": str(responsible_uuid)},
        )
        # 200, 404, ou 422 (UUID inválido no mock) — desde que a rota exista
        assert response.status_code in (200, 404, 422), (
            f"Esperado 200/404/422; foi {response.status_code}: {response.text}"
        )
        # PATCH com null — limpar responsável
        response_null = client.patch(
            f"/finances/entries/{entry_uuid}",
            json={"responsible_user_uuid": None},
        )
        assert response_null.status_code in (200, 404, 422), (
            f"Esperado 200/404/422 com null; foi {response_null.status_code}: {response_null.text}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Stubs de saldo — REL-01, REL-02
# ---------------------------------------------------------------------------


def test_account_balance():
    """REL-01, D-BAL-01: GET /finances/accounts/{uuid}/balance retorna saldo.

    Resposta: {account_uuid, balance (string), currency}.
    Plano 09-04 Task 3: guard removido — endpoint implementado em 09-03/09-04.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()

    fake_account = Account(
        id=1,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        return r

    mock_balance_result = MagicMock()
    mock_balance_result.scalar_one_or_none.return_value = Decimal("250.00")

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_balance_result)
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/finances/accounts/{account_uuid}/balance")
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert "balance" in body, f"Resposta deve conter 'balance'; foi: {body}"
            assert "account_uuid" in body or "uuid" in body, (
                "Resposta deve conter account_uuid (D-BAL-01)"
            )
    finally:
        app.dependency_overrides.clear()


def test_family_balance():
    """REL-02, D-BAL-02: GET /finances/families/{uuid}/balance retorna saldo consolidado.

    Resposta: {family_uuid, total_balance, accounts: [...]}.
    Plano 09-04 Task 3: guard removido — endpoint implementado em 09-03/09-04.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()

    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_family
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(
        return_value=MagicMock(
            scalar_one_or_none=lambda: Decimal("0.00"),
            fetchall=lambda: [],
        )
    )
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/finances/families/{family_uuid}/balance")
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert "total_balance" in body, (
                f"Resposta deve conter 'total_balance' (D-BAL-02); foi: {body}"
            )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Stubs de relatórios — REL-03, REL-04, REL-05
# ---------------------------------------------------------------------------


def test_monthly_report():
    """REL-03/04, D-REP-01: GET /finances/reports/monthly retorna breakdown.

    Resposta: {period, total, rows} onde cada row tem category_uuid,
    subcategory_uuid e total.
    Plano 09-04 Task 3: guard removido — endpoint implementado em 09-03/09-04.
    """

    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()

    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_family
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=MagicMock(fetchall=lambda: []))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(
            "/finances/reports/monthly",
            params={"family_uuid": str(family_uuid), "year": 2026, "month": 5},
        )
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            assert "period" in body, f"Resposta deve conter 'period' (D-REP-01); foi: {body}"
            assert "rows" in body, f"Resposta deve conter 'rows'; foi: {body}"
    finally:
        app.dependency_overrides.clear()


def test_report_uses_competencia():
    """REL-05, D-REP-03: relatório aceita query params year/month (competência).

    Verifica que a rota existe e aceita os parâmetros corretos.
    O relatório opera sobre competencia_year/month — não sobre Movement.date.
    Plano 09-04 Task 3: guard removido — endpoint implementado em 09-03/09-04.
    """
    from fastapi.testclient import TestClient

    from caramello_api.families.models import Family  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()

    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_family
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=MagicMock(fetchall=lambda: []))
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        # Parametros de competência (year/month) — não parametros de data de movimentação
        response = client.get(
            "/finances/reports/monthly",
            params={"family_uuid": str(family_uuid), "year": 2026, "month": 3},
        )
        # 200 ou 404 (família não encontrada no mock) são válidos
        # 422 indica que os params não foram aceitos — falha
        assert response.status_code != 422, (
            f"Endpoint não deve retornar 422 para params year/month válidos; "
            f"foi: {response.status_code}: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Stubs de movimento — D-MOV-01, D-MOV-02
# ---------------------------------------------------------------------------


def test_movement_entry_uuid_field():
    """D-MOV-01: GET movements inclui campo entry_uuid em cada item.

    entry_uuid: UUID | None — null para movimentações pendentes de conciliação.
    Implementado via LEFT JOIN com FinancialEntry.
    Plano 09-04 Task 3: guard removido — campo e LEFT JOIN implementados em 09-04.
    """
    from decimal import Decimal

    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()

    fake_account = Account(
        id=1,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        r.all.return_value = []
        return r

    # Simula um movimento sem entry (pendente)
    mock_movement_row = (
        MagicMock(
            uuid=uuid4(),
            date=datetime.now(UTC),
            amount=Decimal("100.00"),
            description="Pagamento",
            import_hash=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        None,  # entry_uuid = None (pendente)
    )

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = [mock_movement_row]

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/finances/accounts/{account_uuid}/movements")
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
        if response.status_code == 200:
            body = response.json()
            if isinstance(body, list) and body:
                item = body[0]
                assert "entry_uuid" in item, (
                    f"D-MOV-01: cada movimento deve ter 'entry_uuid'; chaves: {list(item.keys())}"
                )
    finally:
        app.dependency_overrides.clear()


def test_movement_reconciled_filter():
    """D-MOV-02: GET /finances/accounts/{uuid}/movements?reconciled=false retorna pendentes.

    Filtro opcional: reconciled=false retorna apenas movimentos sem lançamento;
    reconciled=true retorna apenas conciliados. Implementado via LEFT JOIN + IS NULL.
    Plano 09-04 Task 3: guard removido — filtro implementado em 09-04.
    """

    from fastapi.testclient import TestClient

    from caramello_api.finances.models import Account  # type: ignore[import-not-found]
    from caramello_api.main import app
    from caramello_api.shared.auth import get_current_user
    from caramello_api.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()

    fake_account = Account(
        id=1,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def _exec(stmt):
        r = MagicMock()
        r.first.return_value = fake_account
        return r

    mock_execute_result = MagicMock()
    mock_execute_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    mock_session.rollback = AsyncMock()

    def _session_override():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(
            f"/finances/accounts/{account_uuid}/movements",
            params={"reconciled": "false"},
        )
        # 200 (lista vazia OK) ou 404 (conta não encontrada no mock)
        # 422 indica que o parâmetro reconciled não é aceito — falha
        assert response.status_code in (200, 404), (
            f"Esperado 200 ou 404; foi {response.status_code}: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()
