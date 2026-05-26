---
phase: "03"
plan: "06"
subsystem: generator,models,tests
tags: [mapper-fix, sqlalchemy, sqlmodel, m2m-relationship, xfail-cleanup]
dependency_graph:
  requires: [03-05]
  provides: [mapper-funcional, configure_mappers-ok, testes-destravados]
  affects: [src/caramello/user/models.py, src/caramello/family/models.py, scripts/generate_code.py]
tech_stack:
  added: [sa_relationship_kwargs-secondary-string]
  patterns: [cross-domain-m2m-via-secondary-string, no-from-__future__-in-models]
key_files:
  created: []
  modified:
    - scripts/generate_code.py
    - src/caramello/user/models.py
    - src/caramello/family/models.py
    - src/caramello/family/router.py
    - src/caramello/main.py
    - tests/test_auth.py
    - tests/test_generator.py
    - tests/test_user_operations.py
decisions:
  - "Cross-domain M:M via sa_relationship_kwargs secondary como string (não late-bind pós-classe)"
  - "Models gerados não emitem from __future__ import annotations (mapper SQLAlchemy quebra com lazy annotations)"
  - "user_operations.router registrado antes de user_router em main.py (prioridade de rota estática /user/me)"
metrics:
  duration_minutes: 180
  tasks_completed: 3
  files_modified: 8
  completed_date: "2026-05-26"
---

# Phase 03 Plan 06: Corrigir Mapper SQLAlchemy e Destravar Testes

Corrige bug crítico de mapper SQLAlchemy (`configure_mappers()` falhava com `NoForeignKeysError`/`InvalidRequestError`) no relacionamento M:M cross-domain `User.families`, corrige anotação incorreta `_: Family = Depends()` nos routers, e remove marcas `@pytest.mark.xfail` obsoletas dos testes.

## Tasks Executadas

| Task | Nome | Commit | Arquivos |
|------|------|--------|---------|
| 1 | Adicionar `late_bound_types` em `generate_relationships` para emitir `# noqa: UP037` | `9326c0d` | `scripts/generate_code.py` |
| 2 | Corrigir template de router para emitir `_: User = Depends(get_current_user)` | `b37e46c` | `scripts/generate_code.py` |
| 3 | Corrigir mapper SQLAlchemy via `sa_relationship_kwargs secondary`, regenerar, destravar testes | `0a04966` | 8 arquivos |

## Desvios do Plano

### Problemas Auto-corrigidos

**1. [Rule 1 - Bug] Abordagem do plano (# noqa: UP037 apenas) insuficiente para corrigir o mapper**

- **Encontrado durante:** Task 3 — investigação da causa raiz real
- **Problema:** O plano assumia que adicionar `# noqa: UP037` seria suficiente para preservar aspas em `list["Family"]` e corrigir o mapper. A investigação revelou dois problemas relacionados:
  1. Com `from __future__ import annotations`, a anotação inteira `list["Family"]` vira a string lazy `'list["Family"]'` — `get_origin('list["Family"]')` retorna `None` (string não é GenericAlias), então SQLAlchemy não consegue extrair o tipo `Family`
  2. O late-bind pós-criação de classe (`User.__sqlmodel_relationships__["families"].link_model = FamilyMember`) não propaga para o `RelationshipProperty` do SQLAlchemy (já criado com `secondary=None` no metaclass `__new__`)
- **Solução:** Usar `sa_relationship_kwargs={"secondary": "family_member"}` no `Relationship()` de `User.families` — SQLAlchemy resolve a tabela pelo nome via metadata, sem necessidade de importar `FamilyMember` em `user/models.py`. Remover `from __future__ import annotations` de todos os models gerados.
- **Arquivos modificados:** `scripts/generate_code.py` (função `_consolidate_models`, `generate_relationships`, `generate_models`), `src/caramello/user/models.py`
- **Commit:** `0a04966`

**2. [Rule 1 - Bug] `GET /user/me` retornava 422 por conflito de rota com `GET /user/{uuid}`**

- **Encontrado durante:** Task 3 — execução de `test_get_me_returns_user_fields`
- **Problema:** Em `main.py`, `user_router.router` (com `GET /user/{uuid}`) era registrado antes de `user_operations.router` (com `GET /user/me`). FastAPI correspondia `/user/me` ao handler `{uuid}` com `uuid="me"`, causando erro 422.
- **Solução:** Inverter a ordem de registro — `user_operations.router` antes de `user_router.router`.
- **Arquivos modificados:** `src/caramello/main.py`
- **Commit:** `0a04966`

**3. [Rule 2 - Funcionalidade ausente] `test_get_me_returns_user_fields` usava context manager que dispara lifespan Keycloak**

- **Encontrado durante:** Task 3 — teste falhava com `ConnectError` ao tentar conectar ao Keycloak durante startup
- **Problema:** O teste usava `with TestClient(app) as client:` que dispara o lifespan (`fetch_jwks()` tenta conectar ao Keycloak). O fixture `client` existente não dispara o lifespan.
- **Solução:** Alterar para `client = TestClient(app)` (sem context manager) no `test_get_me_returns_user_fields`, consistente com o fixture `client` existente.
- **Arquivos modificados:** `tests/test_user_operations.py`
- **Commit:** `0a04966`

**4. [Rule 2 - Funcionalidade ausente] Testes do generator testavam presença de `from __future__` (comportamento antigo)**

- **Encontrado durante:** Task 3 — testes XFAIL por razão incorreta após mudança de design
- **Problema:** `test_user_models_in_user_domain` e `test_generated_code_uses_modern_types` asseveravam `from __future__ import annotations` no código gerado — comportamento intencionalmente removido pelo fix do mapper.
- **Solução:** Atualizar asserções para verificar ausência de `from __future__` (e adicionar comentário explicativo). Remover `@pytest.mark.xfail` obsoletos de todos os testes do generator que agora passam.
- **Arquivos modificados:** `tests/test_generator.py`
- **Commit:** `0a04966`

## Decisões Tomadas

### Estratégia para M:M cross-domain sem import circular

O SQLAlchemy suporta `secondary` como string de nome de tabela (resolvido lazily via metadata durante `configure_mappers()`). Isso elimina a necessidade de importar `FamilyMember` em `user/models.py`, resolvendo tanto o import circular quanto o problema de late-bind pós-criação de classe.

### Remoção de `from __future__ import annotations` dos models gerados

Com `from __future__`, todas as anotações de classe viram strings lazy. O SQLModel usa `get_origin()` e `get_args()` para extrair o tipo da anotação de Relationship — mas `get_origin('list["Family"]')` retorna `None` porque uma string não é um `GenericAlias`. Sem `from __future__`, `list["Family"]` é avaliado como `list["Family"]` (GenericAlias) em runtime: `get_origin()` retorna `list`, `get_args()` retorna `('Family',)`, e SQLAlchemy resolve `'Family'` via class registry.

### Mecanismo de duas passagens removido

O mecanismo de `pending_late_bind_assignments` e segunda passagem do gerador foi completamente removido, simplificando o código. A abordagem `sa_relationship_kwargs` resolve o problema em uma única passagem.

## Verificações Pós-Execução

```
configure_mappers(): MAPPER_OK
grep -c "noqa: UP037" src/caramello/user/models.py  -> 2
grep -c "_: User = Depends" src/caramello/family/router.py  -> 10
uv run ruff check src/  -> All checks passed!
uv run mypy src/  -> Success: no issues found in 14 source files
uv run pytest tests/  -> 16 passed, 1 skipped
bin/generate_code (idempotência)  -> sem mudanças na segunda execução
```

## Advertências SQLAlchemy (Não Críticas)

O SQLAlchemy emite SAWarning sobre `overlaps` entre `FamilyMember.user`, `FamilyMember.family` e `User.families` (todos escrevem para as mesmas colunas FK de `family_member`). Esses warnings são informativos e não impedem o funcionamento. A correção seria adicionar `overlaps="families"` ao `FamilyMember.user` e `overlaps="family"` ao `FamilyMember.family`, e inverso para `Family.members`. Isso pode ser feito na DSL futuramente (plano 03-07 ou além).

## ROADMAP.md SC2

Verificação no-op: SC2 já estava correto (`models.py (ORM + schemas Read/Create/Update)`). Nenhuma edição necessária.

## Stubs Conhecidos

Nenhum. Todos os relacionamentos estão corretamente configurados.

## Threat Flags

Nenhum novo endpoint ou superfície de ataque introduzido neste plano.

## Self-Check: PASSED

- `scripts/generate_code.py`: FOUND
- `src/caramello/user/models.py`: FOUND
- `src/caramello/family/models.py`: FOUND
- `src/caramello/main.py`: FOUND
- Commits 9326c0d, b37e46c, 0a04966: FOUND
