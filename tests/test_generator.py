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
    """Wave 1 (Plan 02): dsl/entities/user.yaml contém `domain: user`."""
    data = yaml.safe_load((DSL_ENTITIES_DIR / "user.yaml").read_text())
    assert data.get("domain") == "user", (
        f"user.yaml deve declarar domain: user; encontrado: {data.get('domain')!r}"
    )


def test_family_yamls_have_domain_field():
    """Wave 1 (Plan 02): family*.yaml declaram domain: family."""
    for fname in ("family.yaml", "family_member.yaml", "family_invitation.yaml"):
        data = yaml.safe_load((DSL_ENTITIES_DIR / fname).read_text())
        assert data.get("domain") == "family", (
            f"{fname} deve declarar domain: family; encontrado: {data.get('domain')!r}"
        )


def test_operations_user_yaml_exists():
    """Wave 1 (Plan 02): dsl/operations/user.yaml existe e define operação get_me em /user/me."""
    path = DSL_OPERATIONS_DIR / "user.yaml"
    assert path.exists(), f"dsl/operations/user.yaml deve existir em {path}"
    data = yaml.safe_load(path.read_text())
    assert data.get("domain") == "user", (
        f"domain deve ser 'user'; encontrado: {data.get('domain')!r}"
    )
    ops = data.get("operations", [])
    assert len(ops) >= 1, f"deve ter pelo menos 1 operação; encontradas: {len(ops)}"
    op_names = [op["name"] for op in ops]
    assert "get_me" in op_names, f"operação 'get_me' não encontrada em {op_names}"
    get_me = next(op for op in ops if op["name"] == "get_me")
    assert get_me.get("method") == "GET", (
        f"get_me.method deve ser 'GET'; encontrado: {get_me.get('method')!r}"
    )
    assert get_me.get("path") == "/user/me", (
        f"get_me.path deve ser '/user/me'; encontrado: {get_me.get('path')!r}"
    )
    assert get_me.get("description"), "get_me.description não pode ser vazio"


def test_schema_yaml_has_domain_property():
    """Wave 1 (Plan 02): dsl/schema.yaml reconhece o campo domain como propriedade obrigatória."""
    schema_path = REPO_ROOT / "dsl" / "schema.yaml"
    schema = yaml.safe_load(schema_path.read_text())
    assert "domain" in schema.get("properties", {}), (
        "schema.yaml deve listar 'domain' em properties"
    )
    assert "domain" in schema.get("required", []), (
        "schema.yaml deve listar 'domain' em required"
    )


def test_user_models_in_user_domain():
    """Plano 03-06: src/caramello/user/models.py contém class User (mapper fix)."""
    models_path = REPO_ROOT / "src/caramello/user/models.py"
    assert models_path.exists(), "user/models.py deve existir após regeneração"
    content = models_path.read_text()
    assert "class User(SQLModel, table=True):" in content
    # Intencionalmente sem from __future__ import annotations: com from __future__,
    # list["Family"] vira string lazy e SA não consegue resolver o tipo no mapper.
    assert "from __future__ import annotations" not in content


def test_family_models_consolidated():
    """Plano 03-06: family/models.py contém Family, FamilyMember e FamilyInvitation."""
    models_path = REPO_ROOT / "src/caramello/family/models.py"
    assert models_path.exists()
    content = models_path.read_text()
    assert "class Family(SQLModel, table=True):" in content
    assert "class FamilyMember(SQLModel, table=True):" in content
    assert "class FamilyInvitation(SQLModel, table=True):" in content


def test_generated_code_uses_modern_types():
    """Plano 03-06: código gerado usa `str | None` e `list[T]`, não `Optional`/`List`."""
    models_path = REPO_ROOT / "src/caramello/user/models.py"
    content = models_path.read_text()
    assert "Optional[" not in content, "código gerado não deve usar Optional[X]"
    assert "from typing import Optional" not in content
    assert "from typing import List" not in content
    # Intencionalmente sem from __future__ import annotations (mapper fix 03-06)
    assert "from __future__ import annotations" not in content


def test_generated_router_requires_auth():
    """Plano 03-06: router gerado importa get_current_user e usa Depends."""
    router_path = REPO_ROOT / "src/caramello/user/router.py"
    content = router_path.read_text()
    assert "from caramello.shared.auth import get_current_user" in content
    assert "Depends(get_current_user)" in content


def test_user_operations_stub_or_implemented():
    """Plano 03-05: user/operations.py existe com anotação stub ou implemented."""
    ops_path = REPO_ROOT / "src/caramello/user/operations.py"
    assert ops_path.exists()
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line in (
        "# CARAMELLO-GENERATED: stub",
        "# CARAMELLO-GENERATED: implemented",
    ), f"Primeira linha deve ser anotação CARAMELLO-GENERATED; foi: {first_line!r}"


def test_legacy_paths_removed():
    """Plano 03-05: src/caramello/models e src/caramello/api/generated foram removidos."""
    assert not (REPO_ROOT / "src/caramello/models").exists()
    assert not (REPO_ROOT / "src/caramello/api").exists()
