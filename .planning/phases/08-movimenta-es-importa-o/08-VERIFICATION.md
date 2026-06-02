---
phase: 08-movimenta-es-importa-o
verified: 2026-06-02T22:00:00Z
status: human_needed
score: 4/5
overrides_applied: 0
overrides:
  - must_have: "Reimportar o mesmo arquivo não duplica linhas no banco — linhas já existentes ficam com is_duplicate=true"
    reason: "Design redesenhado intencionalmente em D-02 (CONTEXT.md): is_duplicate persistido removido; duplicatas retornadas em potential_duplicates[] para confirmação do usuário, o que satisfaz o objetivo de MOV-04/05 sem inserir registros duplicados. REQUIREMENTS.md §MOV-05 e ROADMAP SC4 estão desatualizados em relação ao CONTEXT.md que explicitamente documenta a substituição."
    accepted_by: ""
    accepted_at: ""
human_verification:
  - test: "Aplicar migration 0003 em banco PostgreSQL real (caramello_dev)"
    expected: "uv run alembic upgrade head executa sem erro; colunas type e is_duplicate ausentes na tabela movement; uv run alembic downgrade -1 reverte sem erro"
    why_human: "Ambiente de CI não tem PostgreSQL disponível — deviation documentada no 08-02-SUMMARY.md. Migration foi verificada estruturalmente mas nunca executada em banco real."
---

# Phase 8: Movimentações + Importação — Relatório de Verificação

**Objetivo da Fase:** Implementar movimentações financeiras (registro individual + importação CSV/OFX/XLSX) com deduplicação inteligente e autenticação familiar, encerrando os requisitos MOV-01..05.

**Verificado:** 2026-06-02T22:00:00Z
**Status:** human_needed
**Re-verificação:** Não — verificação inicial

---

## Conquista do Objetivo

### Verdades Observáveis

| # | Verdade | Status | Evidência |
|---|---------|--------|-----------|
| 1 | POST /finances/accounts/{uuid}/movements registra movimentação individual e retorna uuid (SC1 / MOV-01) | VERIFICADO | `create_movement` em operations.py linha 617; test_create_movement PASSED (201 + uuid) |
| 2 | POST /import com CSV retorna contagem de inseridas vs duplicatas (SC2 / MOV-02) | VERIFICADO | `import_movements_endpoint` linha 742; test_import_csv PASSED; _parse_csv implementado com Sniffer |
| 3 | POST /import com OFX e XLSX também funciona (SC3 / MOV-03) | VERIFICADO | test_import_ofx e test_import_xlsx PASSED; _parse_ofx (fallback iso-8859-1) e _parse_xlsx (read_only=True + wb.close()) implementados |
| 4 | Reimportar o mesmo arquivo não duplica linhas — duplicatas não inseridas (SC4 / MOV-04) | VERIFICADO | test_import_deduplication PASSED (inserted=0); pre-check em lote + on_conflict_do_nothing verificados em services.py linhas 355-421; **AVISO: ROADMAP/REQUIREMENTS têm is_duplicate=true como literal, implementação usa potential_duplicates[] — design D-02 documentado em CONTEXT.md** |
| 5 | Campos monetários persistidos como NUMERIC(15,2) sem float (SC5) | VERIFICADO | Movement.amount = Numeric(15,2) em models.py linha 69; 0 ocorrências de float( em services.py; Decimal(str(...)) em todos os parsers |

**Pontuação:** 5/5 verdades verificadas no código (ver WARNING sobre SC4 abaixo)

---

### WARNING: Desvio de Design Documentado (SC4 / MOV-04 / MOV-05)

**ROADMAP.md SC4:** "Reimportar o mesmo arquivo não duplica linhas no banco — linhas já existentes ficam com `is_duplicate=true`"

**REQUIREMENTS.md MOV-05:** "Movimentações detectadas como duplicatas são marcadas (`is_duplicate=true`) em vez de rejeitadas"

**Implementação real:** Campo `is_duplicate` removido do schema. Duplicatas retornadas em `potential_duplicates[]` para confirmação via `POST /finances/import/confirm`. OFX deduplica definitivamente via `duplicates_skipped`.

**Origem:** Decisão de design D-02, explicitamente documentada em `08-CONTEXT.md`:
> "Campo is_duplicate: bool removido do DSL YAML e da migration. Razão: com a nova estratégia de deduplicação, duplicatas suspeitas nunca são inseridas — são retornadas para confirmação do usuário."

O CONTEXT.md observa explicitamente: "MOV-04/05 foram redesenhados: `is_duplicate=true` substituído por `potential_duplicates[]` para confirmação."

**Impacto:** A intenção funcional de MOV-04 (sem duplicação) e MOV-05 (revisão em vez de rejeição) está totalmente satisfeita pela implementação. O wording literal de ROADMAP SC4 e REQUIREMENTS MOV-05 não foi atualizado para refletir o redesign.

**Ação necessária:** Adicionar override no frontmatter deste VERIFICATION.md com `accepted_by` e `accepted_at` preenchidos para registrar a aceitação do desvio, OU atualizar ROADMAP.md e REQUIREMENTS.md para refletir o design atual.

---

### Artefatos Obrigatórios

| Artefato | Esperado | Status | Detalhes |
|----------|----------|--------|---------|
| `pyproject.toml` | ofxparse>=0.21 e openpyxl>=3.1.5 | VERIFICADO | Linhas 19-20; `uv run python -c "import ofxparse, openpyxl"` → ok; versões: ofxparse 0.21, openpyxl 3.1.5 |
| `tests/test_finances_operations.py` | 10 stubs de teste para MOV-01..05 | VERIFICADO | Todas as 10 funções presentes nas linhas 741-1697; 26/26 testes PASSED |
| `tests/test_services/test_finances_service.py` | 5 stubs de parser puro | VERIFICADO | Arquivo existe; 5/5 testes PASSED (test_parse_csv, test_parse_csv_error_lines, test_parse_csv_abort_threshold, test_compute_hash, test_normalize_description) |
| `dsl/entities/movement.yaml` | Sem type e is_duplicate; amount com sinal | VERIFICADO | Nenhum campo type ou is_duplicate; amount description: "Valor com sinal: positivo=crédito, negativo=débito. NUMERIC(15,2)." |
| `src/caramello/finances/models.py` | Movement sem type/is_duplicate; amount Decimal | VERIFICADO | `hasattr(Movement, 'type')` → False; `hasattr(Movement, 'is_duplicate')` → False; amount = Numeric(15,2) linha 69 |
| `alembic/versions/0003_movement_schema_update.py` | DROP COLUMN type + is_duplicate; down_revision="0002" | VERIFICADO | revision="0003", down_revision="0002"; upgrade() com drop_column("movement","type") e drop_column("movement","is_duplicate"); downgrade() reconstrói com server_default |
| `src/caramello/finances/services.py` | import_movements + parsers + hash + dedup (>120 linhas) | VERIFICADO | 445 linhas; contém ParsedRow, _normalize_description, _compute_hash, _parse_date, _parse_csv, _parse_ofx, _parse_xlsx, import_movements; on_conflict_do_nothing(index_elements=["import_hash"]) linha 420 |
| `src/caramello/finances/operations.py` | Endpoints de Movement + schemas públicos | VERIFICADO | 4 endpoints: POST /movements (l.617), GET /movements (l.690), POST /movements/import (l.742), POST /import/confirm (l.798); 4 schemas: MovementCreatePublic, MovementReadPublic, ImportResultPublic, ConfirmImportPublic |

---

### Verificação de Links-Chave

| De | Para | Via | Status | Detalhes |
|----|------|-----|--------|---------|
| `tests/test_services/test_finances_service.py` | `caramello.finances.services` | `pytest.importorskip` em cada teste | VERIFICADO | 5/5 testes verdes; importorskip retorna módulo; todos os getattr funcionam |
| `alembic/versions/0003_movement_schema_update.py` | migration 0002 | `down_revision="0002"` | VERIFICADO | linha 18: `down_revision: str | Sequence[str] | None = "0002"` |
| `src/caramello/finances/services.py` | `caramello.finances.models.Movement` | `from caramello.finances.models import Movement` | VERIFICADO | linha 23; select(Movement.import_hash) utilizado no pre-check linha 356 |
| `src/caramello/finances/services.py` | tabela movement (banco) | `pg_insert + on_conflict_do_nothing` | VERIFICADO | `on_conflict_do_nothing(index_elements=["import_hash"])` linha 420 |
| `src/caramello/finances/operations.py` | `caramello.finances.services.import_movements` | `from caramello.finances.services import import_movements` | VERIFICADO | linha 30; chamado em import_movements_endpoint linha 769 |
| `src/caramello/finances/operations.py` | `_require_family_access` | `await _require_family_access(...)` | VERIFICADO | chamado em todos os 4 endpoints de Movement (linhas 641, 712, 764, 819) |

---

### Rastreamento de Data-Flow (Nível 4)

| Artefato | Variável de Dados | Fonte | Produz Dados Reais | Status |
|----------|-------------------|-------|--------------------|--------|
| `operations.py: create_movement` | `db_movement` | `session.add + commit + refresh` | Sim — ORM insert + refresh | FLOWING |
| `operations.py: list_movements` | `movements` | `session.execute(select(Movement)...)` com limit/offset/filtros | Sim — query real com filtros | FLOWING |
| `operations.py: import_movements_endpoint` | `service_result` | `import_movements()` em services.py | Sim — parsers + pg_insert + session.execute para recuperar inseridas | FLOWING |
| `operations.py: confirm_import` | `inserted_movements` | `session.add + commit + refresh` para cada movimento | Sim — insert com import_hash=None (P4) | FLOWING |
| `services.py: import_movements` | `existing_hashes` | `session.execute(select(Movement.import_hash).where(.in_(all_hashes)))` | Sim — query real via session.execute (não session.exec) (P8) | FLOWING |

---

### Verificações Comportamentais (Spot-Checks)

| Comportamento | Comando | Resultado | Status |
|---------------|---------|-----------|--------|
| ofxparse e openpyxl instaláveis | `uv run python -c "import ofxparse, openpyxl"` | ofxparse 0.21, openpyxl 3.1.5 | PASS |
| Movement sem type/is_duplicate | `uv run python -c "from caramello.finances.models import Movement; print(hasattr(Movement,'type'), hasattr(Movement,'is_duplicate'))"` | False False | PASS |
| import_movements é coroutine | `uv run python -c "import inspect; from caramello.finances.services import import_movements; print(inspect.iscoroutinefunction(import_movements))"` | True | PASS |
| Zero float em campo monetário | `grep -c "float(" src/caramello/finances/services.py` | 0 | PASS |
| Zero session.exec em queries de lote | `grep -c "session.exec(" src/caramello/finances/services.py` | 0 | PASS |
| 26 testes verdes | `uv run python -m pytest tests/test_finances_operations.py tests/test_services/test_finances_service.py -q` | 26 passed, 5 warnings in 1.43s | PASS |
| NUMERIC(15,2) sem float | `uv run python -c "from caramello.finances.models import Movement; print(Movement.__table__.c.amount.type)"` | NUMERIC(15, 2) | PASS |
| Decimal aritmética correta | `uv run python -c "from decimal import Decimal; print(Decimal('0.10') + Decimal('0.20') == Decimal('0.30'))"` | True | PASS |

---

### Cobertura de Requisitos

| Requisito | Plano(s) | Descrição | Status | Evidência |
|-----------|----------|-----------|--------|-----------|
| MOV-01 | 08-02, 08-04 | Registro individual: tipo crédito/débito via sinal de amount, data, valor, descrição | SATISFEITO | POST /finances/accounts/{uuid}/movements; test_create_movement PASSED (201 + uuid); 409 com existing_uuid para duplicata |
| MOV-02 | 08-01, 08-03, 08-04 | Importação em lote via CSV | SATISFEITO | POST /import?format=csv; _parse_csv com Sniffer; test_import_csv PASSED |
| MOV-03 | 08-01, 08-03, 08-04 | Importação via OFX ou XLSX | SATISFEITO | _parse_ofx (FITID + fallback iso-8859-1) e _parse_xlsx (read_only=True + wb.close()); test_import_ofx e test_import_xlsx PASSED |
| MOV-04 | 08-02, 08-03, 08-04 | Deduplicação — reimportar não cria duplicatas | SATISFEITO | Pre-check em lote + on_conflict_do_nothing; test_import_deduplication PASSED (inserted=0 para reimportação) |
| MOV-05 | 08-02, 08-03, 08-04 | Duplicatas marcadas para revisão (não rejeitadas) | SATISFEITO (desvio de design) | potential_duplicates[] em vez de is_duplicate=true; POST /import/confirm para inserção manual; test_import_potential_duplicates e test_import_confirm PASSED |

**Requisitos Órfãos (fora do PLAN frontmatter mas mapeados para Phase 8 em REQUIREMENTS.md):** nenhum — todos os 5 IDs mapeados para Phase 8 foram cobertos pelos planos 08-02 e 08-04.

---

### Anti-Padrões Encontrados

| Arquivo | Linha | Padrão | Severidade | Impacto |
|---------|-------|--------|-----------|---------|
| Nenhum | — | Nenhum TBD/FIXME/XXX encontrado em arquivos modificados | — | — |

Varredura realizada em: `services.py`, `operations.py`, `models.py`, `0003_movement_schema_update.py`, `movement.yaml`

**Advertências não-blocantes:**
- `ofxparse` emite `DeprecationWarning: findAll deprecated since BeautifulSoup 4.0` nos testes de OFX. Não afeta funcionalidade na versão atual; será resolvido na próxima versão maior do ofxparse (fora do escopo desta fase).

---

### Verificação Humana Necessária

#### 1. Aplicar migration 0003 em banco PostgreSQL real

**Teste:** No ambiente de desenvolvimento com `caramello_dev` acessível, executar:
```
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```
**Esperado:** Cada comando termina com exit 0; colunas `type` e `is_duplicate` ausentes na tabela `movement` após upgrade; recriadas após downgrade; removidas novamente após segundo upgrade.

**Por que humano:** O ambiente de CI não tem PostgreSQL disponível. A migration foi verificada estruturalmente (AST parse, grep de conteúdo, alembic history) mas o ciclo upgrade/downgrade em banco real não foi executado. Isso é confirmado como desvio de ambiente no 08-02-SUMMARY.md: "ambiente de CI/worktree não tem PostgreSQL disponível — tentativa de conexão retornou [Errno 111]".

---

### Resumo dos Gaps

Nenhum gap bloqueador de código encontrado. A fase entregou toda a implementação funcional com 26/26 testes verdes.

**Pendência de processo:**
1. Migration 0003 precisa ser aplicada manualmente em banco real (`caramello_dev`) antes de usar os endpoints de Movement em ambiente de desenvolvimento — operação de 2 minutos.
2. ROADMAP SC4 e REQUIREMENTS MOV-05 têm wording desatualizado (`is_duplicate=true`) que não reflete o design D-02 adotado. Recomenda-se atualizar os documentos OU adicionar o override acima com `accepted_by`/`accepted_at` preenchidos.

---

*Verificado: 2026-06-02T22:00:00Z*
*Verificador: Claude (gsd-verifier)*
