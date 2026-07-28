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
    assert "domain" in schema.get("required", []), "schema.yaml deve listar 'domain' em required"


def test_user_models_in_user_domain():
    """users/models.py contém a classe de tabela SQLAlchemy `User`."""
    models_path = REPO_ROOT / "src/caramello_api/users/models.py"
    assert models_path.exists(), "users/models.py deve existir após regeneração"
    content = models_path.read_text()
    assert "class User(Base):" in content
    assert "from caramello_api.shared.base import Base" in content
    assert "from sqlalchemy.orm import Mapped, mapped_column, relationship" in content
    assert "mapped_column(" in content, "colunas devem usar mapped_column()"
    # `from __future__ import annotations` é OBRIGATÓRIO no shape SQLAlchemy 2:
    # a biblioteca resolve as anotações PEP 563 por conta própria e encontra as
    # entidades pelo class registry. (Sob SQLModel isso era proibido, porque ele
    # lia a anotação com get_origin/get_args, que devolve None para uma string.)
    assert "from __future__ import annotations" in content


def test_family_models_consolidated():
    """families/models.py contém Family, FamilyMember, FamilyInvitation como tabelas."""
    models_path = REPO_ROOT / "src/caramello_api/families/models.py"
    assert models_path.exists()
    content = models_path.read_text()
    assert "class Family(Base):" in content
    assert "class FamilyMember(Base):" in content
    assert "class FamilyInvitation(Base):" in content


def test_generated_code_uses_modern_types():
    """Código gerado usa `str | None` e `list[T]`, não Optional/List."""
    models_path = REPO_ROOT / "src/caramello_api/users/models.py"
    content = models_path.read_text()
    assert "Optional[" not in content, "código gerado não deve usar Optional[X]"
    assert "from typing import Optional" not in content
    assert "from typing import List" not in content
    assert "from __future__ import annotations" in content
    families_content = (REPO_ROOT / "src/caramello_api/families/models.py").read_text()
    assert "Mapped[str | None]" in families_content, (
        "colunas nullable devem usar `T | None` dentro de Mapped[...]"
    )
    assert "Mapped[list[User]]" in families_content, "coleções devem usar list[T]"


def test_generated_models_carry_no_noqa_up037():
    """O workaround `# noqa: UP037` desapareceu junto com o SQLModel.

    Com SQLAlchemy 2 as aspas em `Mapped[list["Family"]]` são dispensáveis: ruff
    pode removê-las (UP037) e a resolução continua funcionando via class registry.
    """
    for domain in ("users", "families", "finances"):
        content = (REPO_ROOT / f"src/caramello_api/{domain}/models.py").read_text()
        assert "noqa: UP037" not in content, f"{domain}/models.py não deve precisar de noqa UP037"


def test_generated_models_have_no_pydantic_dto():
    """models.py contém APENAS tabelas — nenhum DTO Pydantic."""
    for domain in ("users", "families", "finances"):
        content = (REPO_ROOT / f"src/caramello_api/{domain}/models.py").read_text()
        assert "BaseModel" not in content, f"{domain}/models.py não deve mencionar BaseModel"
        assert "ConfigDict" not in content, f"{domain}/models.py não deve mencionar ConfigDict"
        for suffix in ("Read", "Create", "Update"):
            assert f"{suffix}(" not in content, (
                f"{domain}/models.py não deve declarar DTOs {suffix}"
            )


def test_generated_schemas_live_in_separate_module():
    """Os DTOs vivem em `{domain}/schemas.py` como Pydantic BaseModel puro."""
    expected = {
        "users": ["User"],
        "families": ["Family", "FamilyInvitation"],
        "finances": ["Account", "Movement", "FinancialEntry", "Category", "Subcategory"],
    }
    for domain, entities in expected.items():
        schemas_path = REPO_ROOT / f"src/caramello_api/{domain}/schemas.py"
        assert schemas_path.exists(), f"{domain}/schemas.py deve existir"
        content = schemas_path.read_text()
        assert "from pydantic import BaseModel, ConfigDict" in content
        assert "(Base):" not in content, f"{domain}/schemas.py não deve declarar tabelas"
        assert "mapped_column" not in content, f"{domain}/schemas.py não deve ter colunas"
        for entity in entities:
            assert f"class {entity}Read(BaseModel):" in content
            assert f"class {entity}Create(BaseModel):" in content
            assert f"class {entity}Update(BaseModel):" in content
        # Read models são construídos a partir de instâncias ORM
        assert content.count("model_config = ConfigDict(from_attributes=True)") == len(entities), (
            f"{domain}/schemas.py: cada classe Read deve declarar from_attributes=True"
        )


def test_link_model_has_composite_pk_and_no_surrogate_ids():
    """FamilyMember mantém PK composta pelas duas FKs, sem `id` nem `uuid`."""
    content = (REPO_ROOT / "src/caramello_api/families/models.py").read_text()
    start = content.index("class FamilyMember(Base):")
    end = content.index("class FamilyInvitation(Base):")
    block = content[start:end]
    assert block.count("primary_key=True") == 2, "PK composta = duas colunas primary_key"
    assert 'ForeignKey("user.id")' in block
    assert 'ForeignKey("family.id")' in block
    assert "    id:" not in block, "link model não tem id"
    assert "    uuid:" not in block, "link model não tem uuid"
    assert "autoincrement=True" not in block, "PK composta nunca é autoincrement"
    # Link models não têm DTOs
    schemas = (REPO_ROOT / "src/caramello_api/families/schemas.py").read_text()
    assert "FamilyMemberRead" not in schemas


def test_dual_identifiers_and_timestamps_preserved():
    """Toda entidade não-link tem `id` autoincrement + `uuid` único, e timestamps tz-aware."""
    content = (REPO_ROOT / "src/caramello_api/finances/models.py").read_text()
    assert (
        "id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, "
        "nullable=False)"
    ) in content
    assert (
        "uuid: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False, default=uuid4)"
    ) in content
    assert "DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)" in content
    # updated_at NÃO tem onupdate no nível SQL — os handlers atribuem à mão.
    assert "onupdate" not in content, "updated_at não deve ter onupdate (DDL inalterado)"


def test_expose_as_uuid_splits_table_and_schema():
    """`expose_as_uuid` mantém a coluna int na tabela e expõe só o UUID no schema."""
    models = (REPO_ROOT / "src/caramello_api/finances/models.py").read_text()
    schemas = (REPO_ROOT / "src/caramello_api/finances/schemas.py").read_text()
    assert "responsible_user_id: Mapped[int | None] = mapped_column(" in models
    assert 'ForeignKey("user.id")' in models
    assert "responsible_user_uuid" not in models, "id interno nunca vira UUID na tabela"
    assert "responsible_user_uuid: UUID | None = None" in schemas
    assert "responsible_user_id" not in schemas, "FK inteira nunca vaza para a API pública"


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
    assert domain == "users", f"user.yaml deve declarar domain: users; encontrado: {domain!r}"


def test_family_yamls_domain_is_families():
    """Plano 04-02 (D-09): family*.yaml declaram domain == 'families'."""
    for fname in ("family.yaml", "family_member.yaml", "family_invitation.yaml"):
        data = yaml.safe_load((DSL_ENTITIES_DIR / fname).read_text())
        domain = data.get("domain")
        if domain == "family":
            pytest.xfail(f"Plano 04-02 ainda não rodou — {fname} mantém domain: family")
        assert domain == "families", (
            f"{fname} deve declarar domain: families; encontrado: {domain!r}"
        )


def test_family_invitation_yaml_uses_pending_login_status():
    """Plano 04-02 (D-01): family_invitation.yaml redesenhado — sem invitee_email."""
    data = yaml.safe_load((DSL_ENTITIES_DIR / "family_invitation.yaml").read_text())
    field_names = {f["name"] for f in data.get("fields", [])}
    # Campos antigos REMOVIDOS:
    forbidden = {"invitee_email", "expires_at"}
    present_forbidden = forbidden & field_names
    if present_forbidden:
        pytest.xfail(f"Plano 04-02 ainda não rodou — campos antigos presentes: {present_forbidden}")
    # Campos novos PRESENTES:
    assert "email" in field_names, f"Campo 'email' obrigatório; campos: {field_names}"
    assert "status" in field_names, f"Campo 'status' obrigatório; campos: {field_names}"
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
        pytest.xfail("Plano 04-02 ainda não rodou — prefix antigo ainda emitido")
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
        pytest.xfail("Plano 04-02 ainda não rodou — dsl/operations/family.yaml não existe")
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
    assert not missing, f"Operações faltando em dsl/operations/family.yaml: {missing}"


# ---------------------------------------------------------------------------
# Phase 6 — Plano 01: extensão do gerador para Decimal e filters:
# ---------------------------------------------------------------------------


def test_generator_decimal_emits_numeric():
    """Phase 6 Plan 01 (D-01/SC-7): generate_models emite Numeric(15, 2) para campo Decimal.

    Verifica que:
    - o código gerado contém `mapped_column(Numeric(15, 2), nullable=False)`
    - a anotação é `Mapped[Decimal]`, nunca float
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
        f"O cabeçalho gerado deve importar `from decimal import Decimal`; código gerado:\n{code}"
    )
    assert "amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)" in code, (
        f"O campo Decimal deve gerar `mapped_column(Numeric(15, 2), nullable=False)`; "
        f"código gerado:\n{code}"
    )
    assert "float" not in code, f"nenhum caminho monetário usa float; código gerado:\n{code}"


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
        f"Entidade com filters: deve gerar `__table_args__ = (`; código gerado:\n{code}"
    )
    assert 'Index("ix_movement_account_id", "account_id")' in code, (
        f"Deve gerar Index para filtro simples `account_id`; código gerado:\n{code}"
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
            f"{fname} deve declarar domain: finances; encontrado: {data.get('domain')!r}"
        )


def test_finances_models_no_float():
    """Phase 6 Plan 02 (SC-6): finances/models.py e schemas.py não usam float.

    Nenhum caminho monetário toca ponto flutuante: a coluna é Numeric(15, 2) e
    a anotação é Decimal, tanto na tabela quanto no DTO.
    """
    for name in ("models.py", "schemas.py"):
        path = REPO_ROOT / f"src/caramello_api/finances/{name}"
        assert path.exists(), f"src/caramello_api/finances/{name} deve existir"
        content = path.read_text()
        assert "float" not in content, (
            f"finances/{name} não deve conter `float` em nenhuma forma; "
            "valores monetários são Decimal / Numeric(15, 2)"
        )
    models_content = (REPO_ROOT / "src/caramello_api/finances/models.py").read_text()
    assert "Numeric(15, 2)" in models_content, (
        "models.py deve conter `Numeric(15, 2)` para campos monetários (SC-6)"
    )
    assert "Mapped[Decimal]" in models_content, "a coluna amount deve ser Mapped[Decimal]"
    schemas_content = (REPO_ROOT / "src/caramello_api/finances/schemas.py").read_text()
    assert "amount: Decimal" in schemas_content, "o DTO expõe amount como Decimal"


def test_finances_models_import_ok():
    """Phase 6 Plan 02 (SC-4): models e schemas de finances importam sem erro.

    Verifica que o código gerado é importável e que o mapeamento SQLAlchemy
    configura (um erro de forward reference só aparece em configure_mappers).
    """
    import importlib

    from sqlalchemy.orm import configure_mappers

    try:
        for module in (
            "caramello_api.users.models",
            "caramello_api.families.models",
            "caramello_api.finances.models",
            "caramello_api.finances.schemas",
        ):
            mod = importlib.import_module(module)
            assert mod is not None, f"{module} importado deve ser não-nulo"
    except ImportError as exc:
        raise AssertionError(f"import do código gerado levantou ImportError: {exc}") from exc

    configure_mappers()


def test_generated_router_uses_sqlalchemy_execute():
    """O router gerado usa session.execute + .scalars(), nunca session.exec."""
    for domain in ("users", "families", "finances"):
        content = (REPO_ROOT / f"src/caramello_api/{domain}/router.py").read_text()
        assert "from sqlalchemy import select" in content
        assert "from sqlalchemy.ext.asyncio import AsyncSession" in content
        assert "session.exec(" not in content, "session.exec() não existe em SQLAlchemy"
        assert "await session.execute(" in content
        assert ".scalars()" in content, "select de entidade única precisa desembrulhar a Row"
        assert f"from caramello_api.{domain}.schemas import" in content


def test_no_legacy_orm_imports_anywhere():
    """A dependência antiga foi removida: nenhum módulo do projeto a importa."""
    # Montado em duas partes para que este próprio arquivo não case com a busca.
    needle = "sql" + "model"
    for sub in ("src", "tests", "scripts"):
        for path in sorted((REPO_ROOT / sub).rglob("*.py")):
            content = path.read_text()
            assert f"import {needle}" not in content, f"{path} ainda importa {needle}"
            assert f"from {needle}" not in content, f"{path} ainda importa {needle}"
