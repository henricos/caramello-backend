---
phase: 08-movimentacoes-importacao
reviewed: 2026-06-02T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - alembic/versions/0003_movement_schema_update.py
  - dsl/entities/movement.yaml
  - pyproject.toml
  - src/caramello/finances/models.py
  - src/caramello/finances/operations.py
  - src/caramello/finances/services.py
  - tests/test_finances_operations.py
  - tests/test_services/test_finances_service.py
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-06-02T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Esta fase implementa o domínio de movimentações financeiras: modelos, operações CRUD, importação de extratos (CSV/OFX/XLSX), deduplicação por hash e a migração 0003 que remove colunas obsoletas (`type`, `is_duplicate`). A implementação é substantiva e cobre os requisitos D-04 a D-17. Foram encontrados três bloqueadores: uma crash-path de `None` dereference no `get_account`, uma falha silenciosa na contagem de `inserted` pós `on_conflict_do_nothing`, e um commit realizado em loop N×1 no `confirm_import`. Cinco warnings completam o quadro, incluindo comportamento incorreto no threshold de erro CSV e import não utilizado.

---

## Critical Issues

### CR-01: `None` dereference silenciosa em `get_account` quando família não existe

**File:** `src/caramello/finances/operations.py:244-248`

**Issue:** No endpoint `get_account`, a query de família é executada mas o resultado não é verificado antes de chamar `_require_family_access`. Se `family` for `None` (família deletada enquanto a conta ainda existe), a linha 248 usa `family.uuid if family else account_uuid` — mas a chamada de `_require_family_access` na linha 244 já aconteceu com sucesso (usando `db_account.family_id`). O problema real é que o fallback `family_uuid=account_uuid` na linha 248 retorna um UUID **de conta** no campo `family_uuid` da resposta pública, corrompendo silenciosamente o dado. O mesmo padrão existe em `update_account` (linha 299), `get_category` (linha 401), e `update_category` (linha 445).

```python
# Atual — fallback retorna UUID errado se família não encontrada
return AccountReadPublic(
    uuid=db_account.uuid,
    family_uuid=family.uuid if family else account_uuid,  # account_uuid != family_uuid!
    ...
)

# Correto — família deve existir pois FK garante integridade referencial;
# se não existe, é estado inválido que deve ser sinalizado
if family is None:
    raise HTTPException(status_code=404, detail="Família não encontrada")
return AccountReadPublic(
    uuid=db_account.uuid,
    family_uuid=family.uuid,
    ...
)
```

---

### CR-02: Contagem `inserted` incorreta após `on_conflict_do_nothing`

**File:** `src/caramello/finances/services.py:426-437`

**Issue:** Após o `pg_insert(...).on_conflict_do_nothing()`, o código re-seleciona movimentações pelo `import_hash` e usa `len(inserted_movements)` como count de `inserted`. Isso está errado: se ocorreu uma race condition e algumas linhas foram descartadas pelo `on_conflict`, o SELECT vai retornar **menos linhas** do que `len(values)`, mas `inserted` vai refletir o que foi realmente persistido — essa parte está certa. Porém o count de `inserted` na resposta vai incluir linhas que **já existiam** antes desta chamada (inseridas em chamadas anteriores concorrentes e agora re-selecionadas pelo hash). O SELECT busca por `import_hash IN (inserted_hashes)` e essas hashes já estavam presentes na `existing_hashes` checada na linha 358, mas apenas `to_insert` excluiu os já existentes — portanto linhas que sobrevivem ao `on_conflict` mas eram pré-existentes são contadas como `inserted`. Em cenário de alta concorrência, `inserted` pode ser maior que o número de linhas realmente inseridas nesta chamada.

```python
# Correto: comparar o número de linhas retornadas com o total enviado
# e registrar a diferença como race-condition duplicates
movements_result = await session.execute(
    select(Movement).where(Movement.import_hash.in_(inserted_hashes))
)
fetched = movements_result.scalars().all()
# inserted = somente os que não estavam antes (pre-check já isolou to_insert)
# qualquer diferença entre len(values) e len(fetched) é race condition
race_condition_skipped = len(values) - len(fetched)
for mvt in fetched:
    inserted_movements.append({...})
```

---

### CR-03: Commit dentro de loop N×1 em `confirm_import` — risco de estado parcial

**File:** `src/caramello/finances/operations.py:825-848`

**Issue:** O endpoint `confirm_import` faz `session.commit()` dentro do `for` loop, uma vez por movimentação. Se a inserção da movimentação #3 falhar (constraint violation, timeout, etc.), as movimentações #1 e #2 já foram commitadas e não podem ser revertidas. O chamador recebe um erro 500 com dados parcialmente persistidos. Adicionalmente, um loop de 100 movimentações gera 100 commits sequenciais desnecessários.

```python
# Correto: acumular todas as inserções e commitar uma vez ao final
inserted_movements: list[MovementReadPublic] = []

for movement_in in confirm_in.movements:
    date_val = _parse_date(movement_in.date, line=1)
    db_movement = Movement(
        account_id=db_account.id,
        date=date_val,
        amount=movement_in.amount,
        description=movement_in.description,
        import_hash=None,
    )
    session.add(db_movement)

# Um único commit — atômico
await session.commit()

# Refresh de todos após o commit
for db_movement in ...:
    await session.refresh(db_movement)
    inserted_movements.append(...)
```

---

## Warnings

### WR-01: Import não utilizado — `_normalize_description` importado mas nunca chamado

**File:** `src/caramello/finances/operations.py:29`

**Issue:** `_normalize_description` é importado no topo de `operations.py` mas não é referenciado em nenhum lugar do arquivo. O módulo `operations.py` chama diretamente `_compute_hash` (que internamente usa `_normalize_description`), mas não precisa do import direto. Isso pode causar confusão sobre onde a normalização é aplicada.

**Fix:** Remover `_normalize_description` da linha 29 do import.

---

### WR-02: Threshold de erro CSV (D-13) aplica regra de 50% inclusive em vez de estrita

**File:** `src/caramello/finances/services.py:141`

**Issue:** A condição `len(error_lines) / total_data_rows > 0.5` é estritamente maior que 50%. Isso significa que exatamente 50% de falhas (ex: 1 de 2 linhas) **não aborta**, contrariando a spec D-13 que diz ">50% linhas inválidas → 422". O teste `test_parse_csv_error_lines` em `test_finances_service.py` comenta que "como 1/2 linhas falha (50%), pode ou não levantar" — indicando que a spec não foi seguida de forma estrita. O comportamento atual é marginalmente correto segundo D-13 (que especifica _maior que_ 50%), mas é inconsistente com a mensagem de erro que diz "Mais de 50% das linhas falharam". O problema real é que com exatamente 1 linha válida e 1 inválida, o comportamento é ambíguo.

**Fix:** Definir explicitamente o limiar como `>= 0.5` se a intenção for incluir 50% exato, ou documentar que 50% exato passa (comportamento atual). Pelo menos alinhar a mensagem de erro com o comportamento real.

---

### WR-03: `_parse_date` importado repetidamente com `from ... import` dentro de funções

**File:** `src/caramello/finances/operations.py:644,718,721,822`

**Issue:** `_parse_date` é importado dentro do corpo de quatro funções distintas (`create_movement`, `list_movements` duas vezes, `confirm_import`) com `from caramello.finances.services import _parse_date`. Python cacheia imports, então isso não causa problema de desempenho, mas é código desnecessariamente verboso e inconsistente — `_compute_hash`, `import_movements` e `ParsedRow` são importados no topo, mas `_parse_date` é importado de forma dispersa. Isso também impede análise estática e obfusca dependências.

**Fix:** Mover `_parse_date` para o import do topo de `operations.py` junto com os outros símbolos de `services`.

---

### WR-04: `test_finances_router_paths` verifica apenas 6 paths, ignorando os 4 novos endpoints de Movement

**File:** `tests/test_finances_operations.py:97-109`

**Issue:** O teste `test_finances_router_paths` lista um conjunto `expected` fixo de 6 paths (`/finances/accounts`, `/finances/accounts/{account_uuid}`, etc.) que corresponde ao estado da Phase 7. Os quatro endpoints adicionados na Phase 8 (`/finances/accounts/{account_uuid}/movements`, `/finances/accounts/{account_uuid}/movements/import`, `/finances/import/confirm`, e o path POST de movements) não estão no `expected`. O teste passa mesmo que esses endpoints estejam faltando — não detecta regressão no registro de rotas.

**Fix:** Adicionar os novos paths ao conjunto `expected`:
```python
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
```

---

### WR-05: `downgrade()` em 0003 restaura `is_duplicate` com `server_default='false'` mas sem `NOT NULL` constraint na migração 0002 para linhas existentes

**File:** `alembic/versions/0003_movement_schema_update.py:30-37`

**Issue:** A função `downgrade()` usa `server_default="false"` ao restaurar `is_duplicate` como `NOT NULL`. Isso é correto para linhas novas inseridas após o downgrade. Porém, ao fazer o `ADD COLUMN` em uma tabela com linhas existentes sem um `server_default`, o PostgreSQL preencheria `NULL` — mas como `server_default` é fornecido, está correto. A questão é que `type` é restaurado como `NOT NULL` com `server_default='credito'` (string), mas a migração 0002 criou `type` como `AutoString(length=10)` sem enum validation. O `downgrade` recria a coluna com comprimento 10 mas o `server_default` não é uma string SQLAlchemy tipada — será aceito como literal SQL, o que funciona mas é frágil. Não é bloqueador para o caso de uso normal (prod nunca faz downgrade), mas o `server_default` deve ser `sa.text("'credito'")` para ser explicitamente literal SQL seguro.

**Fix:**
```python
op.add_column(
    "movement",
    sa.Column("type", sa.String(length=10), nullable=False,
              server_default=sa.text("'credito'")),
)
op.add_column(
    "movement",
    sa.Column("is_duplicate", sa.Boolean(), nullable=False,
              server_default=sa.text("false")),
)
```

---

## Info

### IN-01: `MovementReadPublic` em `import_movements_endpoint` hardcoda `import_hash=None`

**File:** `src/caramello/finances/operations.py:783`

**Issue:** Na linha 783, `import_hash=None` é sempre atribuído ao montar `MovementReadPublic` para a resposta do endpoint de importação, mesmo que o movimento tenha um hash. O comment diz "D-16: opcional, para debug", mas o resultado é que a resposta de importação nunca retorna o hash, mesmo quando foi calculado e persistido. Clientes que queiram verificar qual hash foi persistido não conseguem.

**Fix:** Usar `import_hash=m.get("import_hash")` se o campo for incluído no dict retornado por `import_movements`, ou remover o comentário que indica que hash é "para debug" se a intenção é sempre omitir.

---

### IN-02: `_parse_ofx_with_errors` silencia todos os erros de parsing OFX

**File:** `src/caramello/finances/services.py:172-177`

**Issue:** O fallback da linha 172-177 captura `except Exception:` sem logar. Se o parsing OFX falhar por razão desconhecida (não apenas encoding), o código silenciosamente tenta o fallback ISO-8859-1, que também pode falhar — e esse segundo erro propaga sem contexto do erro original. Para debugging de arquivos OFX malformados em produção, a ausência de log torna o diagnóstico difícil.

**Fix:** Logar o erro original antes do fallback usando `logging.getLogger(__name__).debug(...)`.

---

### IN-03: `pyproject.toml` declara `sqlmodel>=0.0.38` mas CLAUDE.md documenta versão instalada `0.0.25`

**File:** `pyproject.toml:8`

**Issue:** `pyproject.toml` exige `sqlmodel>=0.0.38` enquanto `CLAUDE.md` (seção Technology Stack) documenta `sqlmodel 0.0.25`. Há divergência entre a documentação do projeto e o constraint declarado. Se o `uv.lock` fixar 0.0.25, o constraint `>=0.0.38` seria violado — indicando que a documentação ou o lockfile estão desatualizados.

**Fix:** Verificar a versão efetivamente instalada via `uv pip show sqlmodel` e atualizar `CLAUDE.md` para refletir a versão real, ou ajustar o constraint em `pyproject.toml`.

---

_Reviewed: 2026-06-02T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
