# Roadmap: Caramello

## Milestones

- ✅ **[v1.0 — Fundação](milestones/v1.0-ROADMAP.md)** — Stack async, auth Keycloak, estrutura por domínios, domínio families, MCP, Docker, testes _(SHIPPED 2026-05-30 · 5 phases · 25 plans)_
- ✅ **[v2.0 — Domínio Financeiro](milestones/v2.0-ROADMAP.md)** — Contas, movimentações (CSV/OFX/XLSX), categorias hierárquicas, conciliação, saldos e relatórios analíticos _(SHIPPED 2026-06-04 · 4 phases · 14 plans)_

Fora de milestone, depois do v2.0: alinhamento do repositório com o template `ai-ready-project-template`. Atravessou os dois módulos e a raiz, e é por isso que este diretório saiu de `apps/api/.planning/` para a raiz. Entre outras coisas trocou SQLModel por SQLAlchemy 2, versionou as rotas de negócio sob `/api/v1`, adotou allowlist de e-mail com validação de audience, criou o módulo `apps/web`, e adicionou a suíte E2E na raiz.

Os arquivos em `milestones/` são registro histórico do que foi entregue e não são atualizados retroativamente: eles descrevem o estado no fechamento de cada milestone, não o estado atual.

---

## Backlog

| Item | Origem | Prioridade |
|------|--------|-----------|
| FAMILY-04: código de convite reutilizável | M1 D-04 | Alta |
| FAMILY-05: solicitação de entrada via convite | M1 D-04 | Alta |
| FAMILY-06: aprovação/rejeição de solicitações | M1 D-04 | Alta |
| MCP-FIN: ferramentas MCP financeiras (D-MCP-01) | M2 deferido | Alta |
| Uma jornada E2E que atravesse o domínio finances — hoje a suíte da raiz não toca nele, então nada prova que suas camadas se conectam de ponta a ponta. Uma jornada representativa basta (criar conta, registrar movimentação, conciliar, conferir saldo); as demais regras seguem cobertas por unitário, conforme a pirâmide em `docs/testing.md` | Alinhamento ao template | Alta |
| UAT do MCP com Bearer token de um Keycloak real (a suíte E2E usa provedor mock, com RS256 real) | M2 | Média |
| Importação OFX com extrato real de banco BR — o fallback ISO-8859-1 nunca foi exercitado com arquivo de verdade | M2 Phase 8 | Média |
| OPS-02: logging estruturado (structlog) | v2 backlog | Média |
| OPS-03: SSL no DATABASE_URL em produção | v2 backlog | Média |
| Prevenir owner removendo a si mesmo, e owner único por família (regras em prd-core.md ainda não implementadas) | prd-core.md | Média |
| Seleção e troca de "família ativa", e saída voluntária de membro (prd-core.md) | prd-core.md | Média |

### Saíram do backlog

- **OPS-01: `GET /health` com ping ao banco** — entregue no alinhamento ao template. O endpoint é público, não versionado, e reporta `database` (via `SELECT 1`) e `data_dir`.
- **OPS-04: CI pipeline (GitHub Actions)** — decidido contra, por ora. Ver "No CI for now" em `docs/architecture.md`: a verificação roda localmente, conduzida pela IA, e o gate de release é o checklist manual de cada módulo. O único workflow que existe publica as imagens no GHCR. Não é para "consertar" a ausência antes dessa discussão acontecer.
- **UAT E2E com Keycloak real + PostgreSQL** — substituído pela suíte `e2e/` na raiz, que provisiona PostgreSQL efêmero e um provedor OIDC mock assinando RS256 de verdade, exercitando o mesmo caminho de JWKS e assinatura da produção. O que resta é o item de MCP acima.

---

> `PROJECT.md` e `STATE.md` foram removidos por estarem defasados a ponto de enganar: descreviam 85 testes onde há 142, Python 3.10+, SQLModel, `compose.yaml` no módulo e migrations até 0004. São arquivos que o GSD regenera a partir do código — `/gsd-onboard` ou `/gsd-new-milestone` os recria contra a realidade atual. O histórico deles está no git.
