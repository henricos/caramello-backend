# Phase 8: Movimentações + Importação - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-02
**Phase:** 08-Movimentações + Importação
**Areas discussed:** Normalização p/ hash, Formato CSV/import, Resposta da importação, GET movimentações + deduplication redesign

---

## Normalização p/ hash

| Option | Description | Selected |
|--------|-------------|----------|
| Conservadora | lowercase + strip + colapsar espaços. Simples, mantém descrição reconhecível. | ✓ |
| Média | Conservadora + remove pontuação e números no final. Melhor para bancos BR com date/time inline. | |
| Claude decide | Implementar conservadora + testes de normalização para fácil ajuste futuro. | |

**User's choice:** Conservadora

---

## Hash — incluir `type` no hash?

| Option | Description | Selected |
|--------|-------------|----------|
| Não incluir type | Seguir ROADMAP: hash de (account_id, date, amount, descr). | |
| Incluir type | Mais preciso: crédito e débito do mesmo valor no mesmo dia são distintos. | |
| Migrar para amount com sinal | Remover campo `type`, usar amount negativo para débito. | ✓ |

**User's choice:** Migrar para amount com sinal (negativo=débito, positivo=crédito)
**Notes:** Usuário questionou se amount deveria ter sinal para simplificar cálculo de saldo. Decisão: remover campo `type` do movement.yaml e usar amount com sinal. Exige ALTER TABLE na migration de Phase 8.

---

## Formato CSV/import

### Separador CSV

| Option | Description | Selected |
|--------|-------------|----------|
| Ponto-e-vírgula | Padrão bancos BR. | |
| Auto-detect | `csv.Sniffer` detecta separador automaticamente. | ✓ |

**User's choice:** Auto-detect

---

### Colunas obrigatórias

| Option | Description | Selected |
|--------|-------------|----------|
| date, amount, description com header | Mínimo funcional com header obrigatório, case-insensitive. | ✓ |
| Colunas por posição | Sem header; ordem fixa. | |

**User's choice:** date, amount, description (com header obrigatório)

---

### Formato de data

| Option | Description | Selected |
|--------|-------------|----------|
| ISO 8601 apenas | YYYY-MM-DD. Sem ambiguidade. | |
| Multi-formato | Aceitar DD/MM/YYYY e YYYY-MM-DD. Cobre extratos BR. | ✓ |

**User's choice:** Multi-formato (DD/MM/YYYY e YYYY-MM-DD)

---

## Resposta da importação

### Shape da resposta

| Option | Description | Selected |
|--------|-------------|----------|
| Contagem + detalhes | inserted, duplicates, errors + movements[] com as inseridas. | ✓ |
| Só contagem | {inserted, duplicates, errors}. Frontend faz GET depois. | |

**User's choice:** Contagem + detalhes (movements[] na resposta)

---

### Identificação do formato

| Option | Description | Selected |
|--------|-------------|----------|
| Query param ?format= | Explícito, sem ambiguidade. | ✓ |
| Content-Type / extensão | Detectar pelo MIME type. Pode errar. | |

**User's choice:** Query param `?format=csv|ofx|xlsx`

---

### Linhas inválidas

| Option | Description | Selected |
|--------|-------------|----------|
| Importar válidas, reportar erros | Linhas inválidas puladas; error_lines na resposta. | ✓ |
| Abortar tudo | Qualquer linha inválida retorna 422. | |

**User's choice:** Importar válidas, reportar erros (máx 50% de erros antes de abortar)

---

## GET movimentações + redesign de deduplicação

### GET nesta fase ou na Phase 9

| Option | Description | Selected |
|--------|-------------|----------|
| Adicionar nesta fase | limit/offset + date_from/date_to. Necessário para verificar importação. | ✓ |
| Deixar para Phase 9 | movements[] na resposta já cobre a verificação. | |

**User's choice:** Adicionar nesta fase

---

### Filtros de listagem

| Option | Description | Selected |
|--------|-------------|----------|
| limit/offset apenas | Simples; filtros de data ficam para Phase 9. | |
| limit/offset + date_from/date_to | Filtro de período já nesta fase. | ✓ |

**User's choice:** limit/offset + date_from/date_to

---

### MovementReadPublic — is_duplicate e account_uuid

**User's input (free text):** "nao vamos chegar a ter duplicidade nas movimentacoes. ao tentar mapear um registro de uma conta em um movimento e perceber que vai duplicar deve ser reportado na conciliacao e nao duplicar nunca. lembrando que podem ser registros identicos e nao duplicados. nao pode ser somente data e valor, precisa de algum tipo de id complementar para ter certeza da duplicacao. em ultimo caso deve ser confirmado pelo usuario se é duplicacao (nao registra novo movimento) ou não (registra novo movimentacao)"

**Implicação:** Redesign completo da estratégia de deduplicação.

---

### Comportamento ao detectar duplicata suspeita

| Option | Description | Selected |
|--------|-------------|----------|
| Não inserir, retornar para confirmação | potential_duplicates[] na resposta + endpoint de confirmação. | ✓ |
| Não inserir, só reportar | Descartados e listados como skipped_suspected_duplicates. Sem confirm endpoint. | |
| Manter is_duplicate=true (ROADMAP original) | Inserir com is_duplicate=true; revisão posterior. | |

**User's choice:** Não inserir, retornar para confirmação — com `POST /import/confirm`

---

### Campo `is_duplicate`

| Option | Description | Selected |
|--------|-------------|----------|
| Remover is_duplicate | Se nunca inserimos duplicatas, campo é desnecessário. | ✓ |
| Manter como audit trail | is_duplicate=true para movimentações confirmadas como não-únicas. | |

**User's choice:** Remover is_duplicate do schema

---

## Claude's Discretion

- Estrutura dos parsers: um arquivo `finances/parsers/` separado ou funções em `finances/services.py`.
- Limiar exato de 50% de erros antes de abortar.
- Padrão de nomenclatura exato dos schemas públicos de Movement.

## Deferred Ideas

- Filtros avançados em GET /movements (por tipo crédito/débito, valor mínimo/máximo) — Phase 9 com relatórios.
- Soft delete de movimentação — depois que o padrão de `is_active` de Account for validado.
- Importação com preview antes de confirmar (dry-run) — mais poderoso mas mais complexo.
