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


@pytest.mark.xfail(
    reason="Wave 4 (Plan 05) regenera com novo generator",
    strict=False,
)
def test_user_models_in_user_domain():
    """Wave 4 (Plan 05): após regeneração, src/caramello/user/models.py contém class User."""  # noqa: E501
    models_path = REPO_ROOT / "src/caramello/user/models.py"
    assert models_path.exists(), "user/models.py deve existir após regeneração"
    content = models_path.read_text()
    assert "class User(SQLModel, table=True):" in content
    assert "from __future__ import annotations" in content


@pytest.mark.xfail(
    reason="Wave 4 (Plan 05) regenera com novo generator",
    strict=False,
)
def test_family_models_consolidated():
    """Wave 4 (Plan 05): family/models.py contém Family, FamilyMember e FamilyInvitation."""  # noqa: E501
    models_path = REPO_ROOT / "src/caramello/family/models.py"
    assert models_path.exists()
    content = models_path.read_text()
    assert "class Family(SQLModel, table=True):" in content
    assert "class FamilyMember(SQLModel, table=True):" in content
    assert "class FamilyInvitation(SQLModel, table=True):" in content


@pytest.mark.xfail(
    reason="Wave 4 (Plan 05) regenera com novo generator",
    strict=False,
)
def test_generated_code_uses_modern_types():
    """Wave 4 (Plan 05): código gerado usa `str | None` e `list[T]`, não `Optional`/`List`."""  # noqa: E501
    models_path = REPO_ROOT / "src/caramello/user/models.py"
    content = models_path.read_text()
    assert "Optional[" not in content, "código gerado não deve usar Optional[X]"
    assert "from typing import Optional" not in content
    assert "from typing import List" not in content
    assert "from __future__ import annotations" in content


@pytest.mark.xfail(
    reason="Wave 4 (Plan 05) regenera router com Depends(get_current_user)",
    strict=False,
)
def test_generated_router_requires_auth():
    """Wave 4 (Plan 05): router gerado importa get_current_user e usa Depends."""
    router_path = REPO_ROOT / "src/caramello/user/router.py"
    content = router_path.read_text()
    assert "from caramello.shared.auth import get_current_user" in content
    assert "Depends(get_current_user)" in content


@pytest.mark.xfail(
    reason="Wave 4 (Plan 05) gera stub de operations.py",
    strict=False,
)
def test_user_operations_stub_or_implemented():
    """Wave 4 (Plan 05): user/operations.py existe com anotação stub ou implemented."""
    ops_path = REPO_ROOT / "src/caramello/user/operations.py"
    assert ops_path.exists()
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line in (
        "# CARAMELLO-GENERATED: stub",
        "# CARAMELLO-GENERATED: implemented",
    ), f"Primeira linha deve ser anotação CARAMELLO-GENERATED; foi: {first_line!r}"


@pytest.mark.xfail(
    reason="Wave 4 (Plan 05) remove diretórios antigos",
    strict=False,
)
def test_legacy_paths_removed():
    """Wave 4 (Plan 05): src/caramello/models e src/caramello/api/generated foram removidos."""  # noqa: E501
    assert not (REPO_ROOT / "src/caramello/models").exists()
    assert not (REPO_ROOT / "src/caramello/api").exists()
