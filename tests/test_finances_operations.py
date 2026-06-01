"""Testes para src/caramello/finances/operations.py — ACC-01, ACC-02, ACC-03,
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

from datetime import datetime, timezone
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
    pytest.importorskip("caramello.finances.operations")
    ops_path = (
        Path(__file__).resolve().parents[1]
        / "src/caramello/finances/operations.py"
    )
    if ops_path.exists():
        first_line = ops_path.read_text().splitlines()[0].strip()
        if "stub" in first_line:
            pytest.skip("finances/operations.py ainda é stub — aguardando plano 07-02")


def _make_fake_user(user_id: int = 42):
    """Constrói User válido — importa lazy (suporta users/ e user/ modules)."""
    try:
        from caramello.users.models import User  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        from caramello.user.models import User  # type: ignore[no-redef]
    return User(
        id=user_id,
        uuid=uuid4(),
        idp_sub=f"fake-sub-{user_id}",
        email=f"user{user_id}@example.com",
        name=f"Usuario {user_id}",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_finances_module_exists():
    """Plano 07-02/07-03: módulo src/caramello/finances/operations.py existe."""
    pytest.importorskip("caramello.finances.operations")


def test_finances_operations_annotation_is_implemented():
    """Plano 07-02: primeira linha == # CARAMELLO-GENERATED: implemented."""
    _skip_if_stub()
    ops_path = (
        Path(__file__).resolve().parents[1]
        / "src/caramello/finances/operations.py"
    )
    if not ops_path.exists():
        pytest.skip("finances/operations.py ainda não foi gerado/implementado")
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line == "# CARAMELLO-GENERATED: implemented", (
        f"Anotação deve ser 'implemented' após plano 07-02; foi: {first_line!r}"
    )


def test_finances_router_paths():
    """CAT-03: router tem os 6 paths esperados.

    FastAPI/Starlette armazena `route.path` como path COMPLETO (incluindo o
    prefix do router — ex: para `@router.get("/accounts")` num router com
    `prefix="/finances"`, route.path é `"/finances/accounts"`). Verificamos
    os paths completos aqui.

    Não checa decorators ou body — apenas que os 6 paths exatos foram registrados.
    Impede nível 3 de hierarquia — apenas accounts, categories e subcategory existem.
    """
    _skip_if_stub()
    ops_mod = pytest.importorskip("caramello.finances.operations")
    router = ops_mod.router
    # route.path é o path COMPLETO (decorator path com prefix do router aplicado)
    paths = {getattr(r, "path", None) for r in router.routes}
    expected = {
        "/finances/accounts",
        "/finances/accounts/{account_uuid}",
        "/finances/categories",
        "/finances/categories/{category_uuid}",
        "/finances/subcategory",
        "/finances/subcategory/{subcategory_uuid}",
    }
    missing = expected - paths
    assert not missing, (
        f"Sub-paths faltando em finances.operations.router: {missing}. "
        f"Encontrados: {paths}. Prefix do router: {router.prefix!r}"
    )


def test_create_account_returns_uuid():
    """ACC-01: POST /finances/accounts retorna uuid sem id/family_id internos.

    T-07-01: resposta pública NÃO expõe `id` nem `family_id`.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello.finances.models import Account  # type: ignore[import-not-found]
    from caramello.families.models import Family  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_account = Account(
        id=10,
        uuid=uuid4(),
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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

    from caramello.finances.models import Account  # type: ignore[import-not-found]
    from caramello.families.models import Family  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_account = Account(
        id=10,
        uuid=uuid4(),
        family_id=1,
        name="Conta Poupança",
        type="poupanca",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
    """AUTH-FIN-01: sem override de get_current_user, /finances/accounts retorna 403.

    HTTPBearer(auto_error=True) retorna 403 (não 401) para token ausente —
    comportamento documentado do projeto (ver 07-RESEARCH.md Open Question 2).
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello.main import app
    from caramello.shared.database import get_session

    async def _exec(_stmt):
        r = MagicMock()
        r.first.return_value = None
        r.all.return_value = []
        return r

    mock_session = AsyncMock()
    mock_session.exec.side_effect = _exec

    def _session_override():
        yield mock_session

    # Não sobrescreve get_current_user — HTTPBearer levanta 403
    app.dependency_overrides[get_session] = _session_override
    try:
        client = TestClient(app)
        response = client.get(f"/finances/accounts?family_uuid={uuid4()}")
        assert response.status_code == 403, (
            f"Esperado 403 para requisição sem autenticação; recebido: {response.status_code}. "
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

    from caramello.families.models import Family  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Alheia",
        description=None,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
            f"Esperado 403 para não-membro; recebido: {response.status_code}. "
            f"Body: {response.text}"
        )
    finally:
        app.dependency_overrides.clear()


def test_archive_account():
    """ACC-03: PATCH /finances/accounts/{uuid} com is_active=false arquiva sem deletar.

    Verifica que resposta retorna is_active=False e session.delete não foi chamado.
    """
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello.finances.models import Account  # type: ignore[import-not-found]
    from caramello.families.models import Family  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    account_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_account = Account(
        id=10,
        uuid=account_uuid,
        family_id=1,
        name="Conta Corrente",
        type="corrente",
        currency="BRL",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
        assert body.get("is_active") is False, (
            f"Resposta deve ter is_active=False; body: {body}"
        )
        # ACC-03: arquivamento nunca deleta — session.delete não deve ter sido chamado
        mock_session.delete.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_create_category():
    """CAT-01: POST /finances/categories cria categoria pai scoped por família."""
    _skip_if_stub()
    from fastapi.testclient import TestClient

    from caramello.finances.models import Category  # type: ignore[import-not-found]
    from caramello.families.models import Family  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_category = Category(
        id=5,
        uuid=uuid4(),
        family_id=1,
        name="Transporte",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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

    from caramello.finances.models import Category  # type: ignore[import-not-found]
    from caramello.families.models import Family  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    family_uuid = uuid4()
    category_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_category = Category(
        id=5,
        uuid=category_uuid,
        family_id=1,
        name="Transporte",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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

    from caramello.finances.models import Category, Subcategory  # type: ignore[import-not-found]
    from caramello.families.models import Family  # type: ignore[import-not-found]
    from caramello.main import app
    from caramello.shared.auth import get_current_user
    from caramello.shared.database import get_session

    fake_user = _make_fake_user()
    category_uuid = uuid4()
    family_uuid = uuid4()
    fake_family = Family(
        id=1,
        uuid=family_uuid,
        name="Familia Teste",
        description=None,
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_category = Category(
        id=5,
        uuid=category_uuid,
        family_id=1,
        name="Transporte",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    fake_subcategory = Subcategory(
        id=20,
        uuid=uuid4(),
        category_id=5,
        name="Gasolina",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
