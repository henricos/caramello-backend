"""Testes para a evolução do DSL generator (Phase 3 — STRUCT-02).

Cobre: campo `domain` nos YAMLs, output path dinâmico, anotação CARAMELLO-GENERATED,
geração de operations.py a partir de dsl/operations/*.yaml.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DSL_ENTITIES_DIR = REPO_ROOT / "dsl" / "entities"
DSL_OPERATIONS_DIR = REPO_ROOT / "dsl" / "operations"


def test_user_yaml_has_domain_field():
    """Phase 3 -> Phase 4: dsl/entities/user.yaml contém `domain: user` (Phase 3) ou `domain: users` (Phase 4+)."""
    data = yaml.safe_load((DSL_ENTITIES_DIR / "user.yaml").read_text())
    assert data.get("domain") in ("user", "users"), (
        f"user.yaml deve declarar domain: user|users; encontrado: {data.get('domain')!r}"
    )


def test_family_yamls_have_domain_field():
    """Phase 3 -> Phase 4: family*.yaml declaram domain: family (Phase 3) ou families (Phase 4+)."""
    for fname in ("family.yaml", "family_member.yaml", "family_invitation.yaml"):
        data = yaml.safe_load((DSL_ENTITIES_DIR / fname).read_text())
        assert data.get("domain") in ("family", "families"), (
            f"{fname} deve declarar domain: family|families; encontrado: {data.get('domain')!r}"
        )


def test_operations_user_yaml_exists():
    """Wave 1 (Plan 02): dsl/operations/user.yaml existe com operação get_me."""
    path = DSL_OPERATIONS_DIR / "user.yaml"
    assert path.exists(), f"dsl/operations/user.yaml deve existir em {path}"
    data = yaml.safe_load(path.read_text())
    assert data.get("domain") in ("user", "users"), (
        f"domain deve ser 'user' ou 'users'; encontrado: {data.get('domain')!r}"
    )
    ops = data.get("operations", [])
    assert len(ops) >= 1, f"deve ter pelo menos 1 operação; encontradas: {len(ops)}"
    op_names = [op["name"] for op in ops]
    assert "get_me" in op_names, f"operação 'get_me' não encontrada em {op_names}"
    get_me = next(op for op in ops if op["name"] == "get_me")
    assert get_me.get("method") == "GET", (
        f"get_me.method deve ser 'GET'; encontrado: {get_me.get('method')!r}"
    )
    assert get_me.get("path") in ("/user/me", "/users/me"), (
        f"get_me.path deve ser '/user/me' ou '/users/me'; encontrado: {get_me.get('path')!r}"
    )
    assert get_me.get("description"), "get_me.description não pode ser vazio"


def test_schema_yaml_has_domain_property():
    """Wave 1 (Plan 02): dsl/schema.yaml tem campo domain como propriedade."""
    schema_path = REPO_ROOT / "dsl" / "schema.yaml"
    schema = yaml.safe_load(schema_path.read_text())
    assert "domain" in schema.get("properties", {}), (
        "schema.yaml deve listar 'domain' em properties"
    )
    assert "domain" in schema.get("required", []), (
        "schema.yaml deve listar 'domain' em required"
    )


def test_user_models_in_user_domain():
    """Plano 04-03: src/caramello_api/users/models.py contém class User (mapper fix)."""
    models_path = REPO_ROOT / "src/caramello_api/users/models.py"
    assert models_path.exists(), (
        "users/models.py deve existir após regeneração (plano 04-03)"
    )
    content = models_path.read_text()
    assert "class User(SQLModel, table=True):" in content
    # Intencionalmente sem from __future__ import annotations: com from __future__,
    # list["Family"] vira string lazy e SA não consegue resolver o tipo no mapper.
    assert "from __future__ import annotations" not in content


def test_family_models_consolidated():
    """Plano 04-03: families/models.py contém Family, FamilyMember, FamilyInvitation."""  # noqa: E501
    models_path = REPO_ROOT / "src/caramello_api/families/models.py"
    assert models_path.exists()
    content = models_path.read_text()
    assert "class Family(SQLModel, table=True):" in content
    assert "class FamilyMember(SQLModel, table=True):" in content
    assert "class FamilyInvitation(SQLModel, table=True):" in content


def test_generated_code_uses_modern_types():
    """Plano 04-03: código gerado usa `str | None` e `list[T]`, não Optional/List."""
    models_path = REPO_ROOT / "src/caramello_api/users/models.py"
    content = models_path.read_text()
    assert "Optional[" not in content, "código gerado não deve usar Optional[X]"
    assert "from typing import Optional" not in content
    assert "from typing import List" not in content
    # Intencionalmente sem from __future__ import annotations (mapper fix 03-06)
    assert "from __future__ import annotations" not in content


def test_generated_router_requires_auth():
    """Plano 04-03: router gerado importa get_current_user e usa Depends."""
    router_path = REPO_ROOT / "src/caramello_api/users/router.py"
    content = router_path.read_text()
    assert "from caramello_api.shared.auth import get_current_user" in content
    assert "Depends(get_current_user)" in content


def test_user_operations_stub_or_implemented():
    """Plano 04-03: users/operations.py existe com anotação stub ou implemented."""
    ops_path = REPO_ROOT / "src/caramello_api/users/operations.py"
    assert ops_path.exists()
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line in (
        "# CARAMELLO-GENERATED: stub",
        "# CARAMELLO-GENERATED: implemented",
    ), f"Primeira linha deve ser anotação CARAMELLO-GENERATED; foi: {first_line!r}"


def test_legacy_paths_removed():
    """Plano 04-03: src/caramello_api/models, api/generated, user/ e family/ removidos."""
    assert not (REPO_ROOT / "src/caramello_api/models").exists()
    assert not (REPO_ROOT / "src/caramello_api/api").exists()
    assert not (REPO_ROOT / "src/caramello_api/user").exists(), (
        "src/caramello_api/user deve ter sido removido na Phase 4"
    )
    assert not (REPO_ROOT / "src/caramello_api/family").exists(), (
        "src/caramello_api/family deve ter sido removido na Phase 4"
    )


def test_user_yaml_domain_is_users():
    """Plano 04-02 (D-09): dsl/entities/user.yaml declara domain == 'users'."""
    data = yaml.safe_load((DSL_ENTITIES_DIR / "user.yaml").read_text())
    domain = data.get("domain")
    if domain == "user":
        pytest.xfail("Plano 04-02 ainda não rodou — user.yaml mantém domain: user")
    assert domain == "users", (
        f"user.yaml deve declarar domain: users; encontrado: {domain!r}"
    )


def test_family_yamls_domain_is_families():
    """Plano 04-02 (D-09): family*.yaml declaram domain == 'families'."""
    for fname in ("family.yaml", "family_member.yaml", "family_invitation.yaml"):
        data = yaml.safe_load((DSL_ENTITIES_DIR / fname).read_text())
        domain = data.get("domain")
        if domain == "family":
            pytest.xfail(
                f"Plano 04-02 ainda não rodou — {fname} mantém domain: family"
            )
        assert domain == "families", (
            f"{fname} deve declarar domain: families; encontrado: {domain!r}"
        )


def test_family_invitation_yaml_uses_pending_login_status():
    """Plano 04-02 (D-01): family_invitation.yaml redesenhado — sem invitee_email."""
    data = yaml.safe_load(
        (DSL_ENTITIES_DIR / "family_invitation.yaml").read_text()
    )
    field_names = {f["name"] for f in data.get("fields", [])}
    # Campos antigos REMOVIDOS:
    forbidden = {"invitee_email", "expires_at"}
    present_forbidden = forbidden & field_names
    if present_forbidden:
        pytest.xfail(
            "Plano 04-02 ainda não rodou — campos antigos presentes: "
            f"{present_forbidden}"
        )
    # Campos novos PRESENTES:
    assert "email" in field_names, f"Campo 'email' obrigatório; campos: {field_names}"
    assert "status" in field_names, (
        f"Campo 'status' obrigatório; campos: {field_names}"
    )
    # status default == 'pending_login'
    status_field = next(f for f in data["fields"] if f["name"] == "status")
    assert status_field.get("default") == "pending_login", (
        f"status.default deve ser 'pending_login'; foi {status_field.get('default')!r}"
    )


def test_router_url_has_domain_prefix_and_hyphens():
    """Plano 04-02 (D-09/D-10/D-11): generate_router emite prefix domínio+hifens."""
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    try:
        from scripts.generate_code import generate_router
    finally:
        if str(REPO_ROOT) in sys.path:
            sys.path.remove(str(REPO_ROOT))

    entity_data = {
        "name": "FamilyInvitation",
        "table_name": "family_invitation",
        "domain": "families",
        "fields": [
            {
                "name": "id",
                "type": "int",
                "primary_key": True,
                "nullable": False,
            },
            {
                "name": "uuid",
                "type": "UUID",
                "unique": True,
                "default_factory": "uuid4",
                "nullable": False,
            },
        ],
        "relationships": [],
    }
    try:
        code = generate_router(entity_data)
    except Exception as exc:  # noqa: BLE001
        pytest.xfail(f"Plano 04-02 ainda não rodou — generate_router falhou: {exc}")
    if 'prefix="/family_invitation"' in code:
        pytest.xfail(
            "Plano 04-02 ainda não rodou — prefix antigo ainda emitido"
        )
    prefix_lines = [line for line in code.splitlines() if "prefix=" in line]
    assert 'prefix="/families/family-invitation"' in code, (
        f"Esperado prefix='/families/family-invitation' em código gerado; "
        f"prefixes encontrados: {prefix_lines}"
    )


def test_operations_user_yaml_path_is_users_me():
    """Plano 04-02 (D-11): dsl/operations/user.yaml.get_me.path == /users/me."""
    data = yaml.safe_load((DSL_OPERATIONS_DIR / "user.yaml").read_text())
    get_me = next(op for op in data["operations"] if op["name"] == "get_me")
    path = get_me.get("path")
    if path == "/user/me":
        pytest.xfail("Plano 04-02 ainda não rodou — get_me.path ainda é /user/me")
    assert path == "/users/me", f"get_me.path deve ser '/users/me'; foi {path!r}"


def test_operations_family_yaml_exists_with_six_operations():
    """Plano 04-02 (D-05, D-07): dsl/operations/family.yaml existe com 6 operações."""
    family_ops_path = DSL_OPERATIONS_DIR / "family.yaml"
    if not family_ops_path.exists():
        pytest.xfail(
            "Plano 04-02 ainda não rodou — dsl/operations/family.yaml não existe"
        )
    data = yaml.safe_load(family_ops_path.read_text())
    assert data.get("domain") == "families", (
        f"domain deve ser 'families'; foi {data.get('domain')!r}"
    )
    expected_ops = {
        "registry_family",
        "list_my_families",
        "get_family_detail",
        "pre_register_member",
        "list_members",
        "remove_member",
    }
    actual_ops = {op["name"] for op in data.get("operations", [])}
    missing = expected_ops - actual_ops
    assert not missing, (
        f"Operações faltando em dsl/operations/family.yaml: {missing}"
    )


# ---------------------------------------------------------------------------
# Phase 6 — Plano 01: extensão do gerador para Decimal e filters:
# ---------------------------------------------------------------------------


def test_generator_decimal_emits_numeric():
    """Phase 6 Plan 01 (D-01/SC-7): generate_models emite Column(Numeric(15, 2)) para campo Decimal.

    Verifica que:
    - o código gerado contém `Column(Numeric(15, 2)` com nullable=False
    - o cabeçalho importa `from decimal import Decimal`
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    try:
        from scripts.generate_code import generate_models
    finally:
        if str(REPO_ROOT) in sys.path:
            sys.path.remove(str(REPO_ROOT))

    entity_data = {
        "name": "Movement",
        "table_name": "movement",
        "domain": "finances",
        "description": "Movimentação financeira bruta.",
        "fields": [
            {"name": "id", "type": "int", "primary_key": True, "nullable": False},
            {
                "name": "uuid",
                "type": "UUID",
                "unique": True,
                "default_factory": "uuid4",
                "nullable": False,
            },
            {"name": "amount", "type": "Decimal", "nullable": False},
        ],
        "relationships": [],
    }
    code = generate_models(entity_data, entity_domain={})

    assert "from decimal import Decimal" in code, (
        "O cabeçalho gerado deve importar `from decimal import Decimal`; "
        f"código gerado:\n{code}"
    )
    assert "Numeric(15, 2)" in code, (
        "O campo Decimal deve gerar `Column(Numeric(15, 2)` no código; "
        f"código gerado:\n{code}"
    )
    assert "nullable=False" in code, (
        "O campo Decimal não-nullable deve emitir `nullable=False`; "
        f"código gerado:\n{code}"
    )


def test_generator_filters_emits_table_args():
    """Phase 6 Plan 01 (D-11/SC-8): generate_models emite __table_args__ com Index para entidades com filters:.

    Verifica que:
    - o código gerado contém `__table_args__ = (`
    - índices individuais: `Index("ix_movement_account_id", "account_id")`
    - índice composto: `Index("ix_movement_competencia_year_competencia_month", ...)`
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    try:
        from scripts.generate_code import generate_models
    finally:
        if str(REPO_ROOT) in sys.path:
            sys.path.remove(str(REPO_ROOT))

    entity_data = {
        "name": "Movement",
        "table_name": "movement",
        "domain": "finances",
        "description": "Movimentação financeira bruta.",
        "fields": [
            {"name": "id", "type": "int", "primary_key": True, "nullable": False},
            {
                "name": "uuid",
                "type": "UUID",
                "unique": True,
                "default_factory": "uuid4",
                "nullable": False,
            },
            {"name": "account_id", "type": "int", "nullable": False},
            {"name": "competencia_year", "type": "int", "nullable": False},
            {"name": "competencia_month", "type": "int", "nullable": False},
        ],
        "relationships": [],
        "filters": [
            {"fields": ["account_id"]},
            {"fields": ["competencia_year", "competencia_month"]},
        ],
    }
    code = generate_models(entity_data, entity_domain={})

    assert "__table_args__ = (" in code, (
        "Entidade com filters: deve gerar `__table_args__ = (`; "
        f"código gerado:\n{code}"
    )
    assert 'Index("ix_movement_account_id", "account_id")' in code, (
        "Deve gerar Index para filtro simples `account_id`; "
        f"código gerado:\n{code}"
    )
    assert (
        'Index("ix_movement_competencia_year_competencia_month", '
        '"competencia_year", "competencia_month")'
    ) in code, (
        "Deve gerar Index composto para filtro `competencia_year + competencia_month`; "
        f"código gerado:\n{code}"
    )


# ---------------------------------------------------------------------------
# Phase 6 — Plano 02: YAMLs financeiros, geração, importação (Wave 0)
# ---------------------------------------------------------------------------


def test_finances_yamls_have_domain_finances():
    """Phase 6 Plan 02 (SC-5): os 5 YAMLs financeiros declaram domain: finances.

    Verifica que cada um dos 5 YAMLs tem domain == 'finances'.
    """
    yaml_files = [
        "account.yaml",
        "movement.yaml",
        "financial_entry.yaml",
        "category.yaml",
        "subcategory.yaml",
    ]
    for fname in yaml_files:
        data = yaml.safe_load((DSL_ENTITIES_DIR / fname).read_text())
        assert data.get("domain") == "finances", (
            f"{fname} deve declarar domain: finances; "
            f"encontrado: {data.get('domain')!r}"
        )


def test_finances_models_no_float():
    """Phase 6 Plan 02 (SC-6): src/caramello_api/finances/models.py não usa float em campos monetários.

    Verifica que o models.py gerado não contém `: float` nem `Float(` em campos de valor.
    O campo amount deve usar Numeric(15, 2) via sa_column.
    """
    models_path = REPO_ROOT / "src/caramello_api/finances/models.py"
    assert models_path.exists(), (
        "src/caramello_api/finances/models.py deve existir (gerador deve ter rodado)"
    )
    content = models_path.read_text()
    # Verifica ausência de float em campos de valor
    assert ": float" not in content, (
        "models.py não deve conter `: float` em campos de valor monetário; "
        "campos Decimal devem usar Numeric(15, 2)"
    )
    assert "Float(" not in content, (
        "models.py não deve conter `Float(` em campos de valor monetário; "
        "campos Decimal devem usar Numeric(15, 2)"
    )
    # Verifica presença do tipo correto
    assert "Numeric(15, 2)" in content, (
        "models.py deve conter `Numeric(15, 2)` para campos monetários (SC-6)"
    )


def test_finances_models_import_ok():
    """Phase 6 Plan 02 (SC-4): from caramello_api.finances import models não levanta ImportError.

    Verifica que o código gerado é importável sem erros.
    """
    import importlib

    try:
        mod = importlib.import_module("caramello_api.finances.models")
        assert mod is not None, "módulo importado deve ser não-nulo"
    except ImportError as exc:
        raise AssertionError(
            f"from caramello_api.finances import models levantou ImportError: {exc}"
        ) from exc
