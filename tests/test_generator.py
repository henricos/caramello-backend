"""Testes para a evolução do DSL generator (Phase 3 — STRUCT-02).

Cobre: campo `domain` nos YAMLs, output path dinâmico, anotação CARAMELLO-GENERATED,
geração de operations.py a partir de dsl/operations/*.yaml.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_user_yaml_has_domain_field():
    """Wave 1 (Plan 02): dsl/entities/user.yaml contém `domain: user`."""
    data = yaml.safe_load((REPO_ROOT / "dsl/entities/user.yaml").read_text())
    assert data.get("domain") == "user", "user.yaml deve declarar domain: user"


def test_family_yamls_have_domain_field():
    """Wave 1 (Plan 02): family*.yaml declaram domain: family."""
    for fname in ("family.yaml", "family_member.yaml", "family_invitation.yaml"):
        data = yaml.safe_load((REPO_ROOT / f"dsl/entities/{fname}").read_text())
        assert data.get("domain") == "family", f"{fname} deve declarar domain: family"


def test_operations_user_yaml_exists():
    """Wave 1 (Plan 02): dsl/operations/user.yaml existe e define operação get_me."""
    path = REPO_ROOT / "dsl/operations/user.yaml"
    assert path.exists(), "dsl/operations/user.yaml deve existir"
    data = yaml.safe_load(path.read_text())
    assert data.get("domain") == "user"
    ops = data.get("operations", [])
    assert any(
        op.get("name") == "get_me" and op.get("path") == "/user/me" for op in ops
    ), "Operação get_me em /user/me deve estar definida"


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
