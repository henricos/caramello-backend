# tests/test_generator.py
# Testes de validação dos artefatos de entrada para o generator DSL.
# Verifica que os YAMLs de entidade e de operações estão corretamente estruturados.

from pathlib import Path

import yaml


DSL_ENTITIES_DIR = Path(__file__).parent.parent / "dsl" / "entities"
DSL_OPERATIONS_DIR = Path(__file__).parent.parent / "dsl" / "operations"


def test_user_yaml_has_domain_field() -> None:
    """Verifica que user.yaml contém o campo domain com valor 'user'."""
    data = yaml.safe_load((DSL_ENTITIES_DIR / "user.yaml").read_text())
    assert data.get("domain") == "user", (
        f"user.yaml deve ter domain='user'; encontrado: {data.get('domain')!r}"
    )


def test_family_yamls_have_domain_field() -> None:
    """Verifica que family.yaml, family_member.yaml e family_invitation.yaml têm domain='family'."""
    family_files = ["family.yaml", "family_member.yaml", "family_invitation.yaml"]
    for fname in family_files:
        data = yaml.safe_load((DSL_ENTITIES_DIR / fname).read_text())
        assert data.get("domain") == "family", (
            f"{fname} deve ter domain='family'; encontrado: {data.get('domain')!r}"
        )


def test_operations_user_yaml_exists() -> None:
    """Verifica que dsl/operations/user.yaml existe e contém a operação get_me."""
    ops_path = DSL_OPERATIONS_DIR / "user.yaml"
    assert ops_path.exists(), f"dsl/operations/user.yaml deve existir em {ops_path}"

    data = yaml.safe_load(ops_path.read_text())
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


def test_schema_yaml_has_domain_property() -> None:
    """Verifica que dsl/schema.yaml reconhece o campo domain como propriedade obrigatória."""
    schema_path = Path(__file__).parent.parent / "dsl" / "schema.yaml"
    schema = yaml.safe_load(schema_path.read_text())

    assert "domain" in schema.get("properties", {}), (
        "schema.yaml deve listar 'domain' em properties"
    )
    assert "domain" in schema.get("required", []), (
        "schema.yaml deve listar 'domain' em required"
    )
