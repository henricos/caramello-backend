---
phase: 08-movimenta-es-importa-o
plan: "03"
subsystem: finances
tags: [services, import, csv, ofx, xlsx, deduplication, hash]
dependency_graph:
  requires: ["08-01", "08-02"]
  provides: ["08-04"]
  affects: ["src/caramello/finances/services.py"]
tech_stack:
  added: []
  patterns:
    - "ParsedRow dataclass para row parseada de extrato"
    - "SHA-256 determinístico com FITID (OFX) ou composto (CSV/XLSX)"
    - "_parse_csv/_parse_csv_with_errors: interface dupla (list vs tuple) para compatibilidade com testes"
    - "lazy import de ofxparse e openpyxl dentro dos parsers"
    - "pg_insert + on_conflict_do_nothing como safety net de concorrência"
    - "session.execute() (não session.exec()) para queries com .in_()"
key_files:
  created:
    - src/caramello/finances/services.py
  modified: []
decisions:
  - "Interface dupla em _parse_csv: versão pública retorna list (compatibilidade com testes 08-01), variante _parse_csv_with_errors retorna tuple(rows, error_lines) para uso em import_movements"
  - "import_movements implementado junto com parsers no mesmo commit — arquivo único services.py"
metrics:
  duration_minutes: 25
  completed_date: "2026-06-02"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 0
---

# Phase 08 Plan 03: Finances Services — Parsers, Hash, Dedup Summary

**One-liner:** Camada de lógica de negócio `finances/services.py` com parsers CSV/OFX/XLSX, hash SHA-256 determinístico (FITID para OFX, composto para CSV/XLSX), normalização de descrição e `import_movements()` com deduplicação em lote via pre-check + `on_conflict_do_nothing`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implementar parsers, hash e normalização (parte pura) | f86f0db | src/caramello/finances/services.py (criado) |
| 2 | Implementar import_movements() com deduplicação em lote | f86f0db | src/caramello/finances/services.py (incluído no commit da Task 1) |

## What Was Built

`src/caramello/finances/services.py` (445 linhas) com:

- `ParsedRow` dataclass: `date`, `amount (Decimal)`, `description`, `fitid (str | None)`
- `_normalize_description(desc)`: strip + lower + colapso de espaços múltiplos (D-06)
- `_compute_hash(account_id, row)`: SHA-256 com `"fitid:{fitid}"` para OFX (D-04) ou `"{account_id}|{date}|{amount}|{desc_norm}"` para CSV/XLSX (D-07)
- `_parse_date(value, line)`: tenta `%Y-%m-%d` depois `%d/%m/%Y`; levanta `ValueError` com número da linha (D-12)
- `_parse_csv(content)`: retorna `list[ParsedRow]` (interface pública); `_parse_csv_with_errors` retorna `tuple` com `error_lines`; `csv.Sniffer` para separador com fallback `csv.excel` (D-10/P7); headers case-insensitive (D-11); threshold 50% (D-13)
- `_parse_ofx(content)` / `_parse_ofx_with_errors`: `ofxparse.OfxParser.parse(BytesIO)`; fallback `iso-8859-1` para bancos BR (P6); `txn.id` como FITID
- `_parse_xlsx(content)` / `_parse_xlsx_with_errors`: `openpyxl.load_workbook(read_only=True)`; `wb.close()` em `finally` (P5); headers case-insensitive
- `import_movements(content, format, account_id, session)`: dispatch por formato; pre-check em lote `session.execute(select(Movement.import_hash).where(.in_(...)))` (P8); OFX com hash existente → `duplicates_skipped` (D-04); CSV/XLSX com hash existente → `potential_duplicates[]` com `existing_movement_uuid` (D-05); `pg_insert.on_conflict_do_nothing(index_elements=["import_hash"])` como safety net (P4); retorna shape D-14

## Verification

```
uv run python -m pytest tests/test_services/test_finances_service.py -q
5 passed in 0.09s
```

```
grep -c "float(" src/caramello/finances/services.py  → 0
grep -v '^#' src/caramello/finances/services.py | grep -c "session.exec("  → 0
import inspect; from caramello.finances.services import import_movements
inspect.iscoroutinefunction(import_movements)  → True
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Interface de retorno de _parse_csv — incompatibilidade com testes existentes**
- **Encontrado durante:** Task 1 (execução dos testes)
- **Problema:** O plano especificava `_parse_csv` retornando `tuple[list[ParsedRow], list[dict]]`, mas o teste `test_parse_csv` criado em 08-01 esperava `list[ParsedRow]` diretamente (sem desempacotar tupla). `len(rows_sc) == 1` falhava porque `len` da tupla era 2.
- **Correção:** Interface dupla — `_parse_csv` pública retorna `list[ParsedRow]` (compatível com os testes); `_parse_csv_with_errors` retorna `tuple` e é usada internamente por `import_movements`. Mesma abordagem replicada para `_parse_ofx` e `_parse_xlsx`.
- **Arquivos modificados:** `src/caramello/finances/services.py`
- **Commit:** f86f0db

**2. [Rule 2 - Funcionalidade ausente] `import_movements` implementado junto com parsers**
- **Encontrado durante:** Planejamento da Task 1
- **Razão:** `import_movements` depende diretamente dos parsers (via `_parse_csv_with_errors`, etc.) e do `_compute_hash`. Implementar ambas as tasks em separado geraria um estado intermediário com o arquivo incompleto. Como as funções são coesas e vivem no mesmo arquivo, foram implementadas juntas no commit da Task 1.
- **Impacto:** Commit único `f86f0db` contém o arquivo completo (Tasks 1 e 2).

## Known Stubs

Nenhum stub encontrado. `import_movements` usa parsers reais (não mocks) e banco real via session. O módulo é totalmente funcional sem dados de placeholder.

## Threat Flags

Nenhuma superfície de segurança nova além do especificado no plano.

## Self-Check: PASSED

- [x] `src/caramello/finances/services.py` existe (445 linhas, acima do mínimo de 120)
- [x] Commit `f86f0db` existe no histórico
- [x] `class ParsedRow` presente
- [x] `def _normalize_description`, `def _compute_hash`, `def _parse_date`, `def _parse_csv`, `def _parse_ofx`, `def _parse_xlsx` presentes
- [x] 0 ocorrências de `float(` em campos monetários
- [x] `Decimal(str(` em pelo menos um parser (3 ocorrências)
- [x] `wb.close()` dentro de bloco `finally`
- [x] `iso-8859-1` presente (fallback OFX P6)
- [x] `async def import_movements(` com parâmetros `content, format, account_id, session`
- [x] `on_conflict_do_nothing(index_elements=["import_hash"])` presente
- [x] `select(Movement.import_hash)` com `.in_(` presente
- [x] 0 ocorrências de `session.exec(` em queries de lote
- [x] Shape D-14 com chaves: `inserted`, `duplicates_skipped`, `potential_duplicates`, `error_lines`, `movements`
- [x] 5/5 testes verdes
