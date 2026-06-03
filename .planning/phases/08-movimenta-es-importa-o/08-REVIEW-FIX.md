---
phase: 08-movimentacoes-importacao
fixed_at: 2026-06-03T00:00:00Z
review_path: .planning/phases/08-movimenta-es-importa-o/08-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 08: Code Review Fix Report

**Fixed at:** 2026-06-03T00:00:00Z
**Source review:** .planning/phases/08-movimenta-es-importa-o/08-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (3 Critical + 5 Warning)
- Fixed: 8
- Skipped: 0

## Fixed Issues

### CR-01: `None` dereference silenciosa em `get_account` quando família não existe

**Files modified:** `src/caramello/finances/operations.py`
**Commit:** 4659b0a
**Applied fix:** Adicionada verificação explícita `if family is None: raise HTTPException(404)` em `get_account`, `update_account`, `get_category` e `update_category`. Removido o fallback incorreto `family.uuid if family else account_uuid` que retornava o UUID da conta no campo `family_uuid`.

---

### CR-02: Contagem `inserted` incorreta após `on_conflict_do_nothing`

**Files modified:** `src/caramello/finances/services.py`
**Commit:** 44a2070
**Applied fix:** Após o SELECT pós-inserção em lote, compara `len(fetched)` com `len(values)`. A diferença (`race_condition_skipped`) é adicionada a `duplicates_skipped`, garantindo que linhas descartadas por race condition via `on_conflict_do_nothing` não sejam contadas como inseridas.

---

### CR-03: Commit dentro de loop N×1 em `confirm_import`

**Files modified:** `src/caramello/finances/operations.py`
**Commit:** a41d1ed
**Applied fix:** Refatorado `confirm_import` para acumular todos os objetos `Movement` na sessão durante o loop sem commitar, realizando um único `await session.commit()` atômico ao final. Refresh de todos os objetos ocorre após o commit único.

---

### WR-01: Import não utilizado — `_normalize_description`

**Files modified:** `src/caramello/finances/operations.py`
**Commit:** 45b1091
**Applied fix:** Removido `_normalize_description` do bloco de imports do topo de `operations.py`. O símbolo não era referenciado diretamente no arquivo.

---

### WR-02: Threshold CSV aplica regra de 50% estrita em vez de inclusiva

**Files modified:** `src/caramello/finances/services.py`
**Commit:** c19f692
**Applied fix:** Alterada a condição de `> 0.5` para `>= 0.5` em `_parse_csv`, alinhando o comportamento com a mensagem de erro ("Mais de 50% das linhas falharam"). Com exatamente 50% de linhas inválidas o lote agora é abortado com 422.

---

### WR-03: `_parse_date` importado dentro do corpo de funções

**Files modified:** `src/caramello/finances/operations.py`
**Commit:** f681db8
**Applied fix:** Adicionado `_parse_date` ao bloco de imports do topo de `operations.py` junto com `_compute_hash`, `import_movements` e `ParsedRow`. Removidos os quatro imports inline dentro dos corpos de `create_movement`, `list_movements` (2×) e `confirm_import`.

---

### WR-04: `test_finances_router_paths` não verifica os 4 novos paths de Movement

**Files modified:** `tests/test_finances_operations.py`
**Commit:** bcb1441
**Applied fix:** Adicionados ao conjunto `expected` os paths `/finances/accounts/{account_uuid}/movements`, `/finances/accounts/{account_uuid}/movements/import` e `/finances/import/confirm`. O teste agora detecta regressão no registro desses endpoints.

---

### WR-05: `downgrade()` usa string literal em vez de `sa.text()` para `server_default`

**Files modified:** `alembic/versions/0003_movement_schema_update.py`
**Commit:** f1aee1d
**Applied fix:** Substituídas as strings `"credito"` e `"false"` por `sa.text("'credito'")` e `sa.text("false")` no `downgrade()` da migração 0003, tornando os valores padrão explicitamente literais SQL.

---

_Fixed: 2026-06-03T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
