# Phase 2: Stack Async - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured em CONTEXT.md — este log preserva as alternativas consideradas.

**Date:** 2026-05-25
**Phase:** 02-stack-async
**Areas discussed:** SQLModel: atualizar versão?, Routers existentes: regenerar agora?, Escopo do generator nesta fase

---

## SQLModel: atualizar versão?

| Option | Description | Selected |
|--------|-------------|----------|
| Atualizar para a mais recente | `uv add sqlmodel@latest` — resolve limitações async na raiz. Risco: breaking changes na API (improvável, versões 0.x tendem a ser conservadoras). | ✓ |
| Manter 0.0.25, adaptar ao que existe | Zero risco de regressão. Pode exigir workarounds pontuais (ex.: usar `session.execute()` do SQLAlchemy puro em alguns casos). | |

**User's choice:** Atualizar para a mais recente
**Notes:** Researcher deve verificar changelog da versão instalada para identificar breaking changes antes do planning. Em particular, verificar se `session.exec()` async ainda é o padrão recomendado na versão mais recente.

---

## Routers existentes: regenerar agora?

| Option | Description | Selected |
|--------|-------------|----------|
| Regenerar na Phase 2 | Após atualizar o generator, rodar `bin/generate_code`. Todo código na repo fica async imediatamente. Consistência: nenhum arquivo sync sobrevive. | ✓ |
| Não regenerar — aguardar Phase 3 | Os 4 routers ficam sync até serem substituídos. A app não está em produção, então consistência não é crítica. Generator fica atualizado e pronto para Phase 3. | |

**User's choice:** Regenerar na Phase 2
**Notes:** Os 4 routers (user, family, family_member, family_invitation) são 100% código gerado e serão reescritos na Phase 3 de qualquer forma, mas o usuário prefere consistência imediata.

---

## Escopo do generator nesta fase

| Option | Description | Selected |
|--------|-------------|----------|
| Mínimo na Phase 2 — domain fica para Phase 3 | Phase 2 = async puro. Generator só muda templates de router (async def, AsyncSession, import de shared/database.py). Phase 3 adiciona domain field e muda output path. Scope limpo por fase. | ✓ |
| Adiantar domain na Phase 2 | Enquanto mexe no generator, adicionar leitura do campo domain e novo output path. Mais trabalho agora, mas Phase 3 começa com generator já pronto. | |

**User's choice:** Mínimo na Phase 2 — domain fica para Phase 3
**Notes:** Usuário pediu explicação mais detalhada antes de decidir. Após clarificação do tradeoff (scope claro por fase vs. adiantar trabalho), optou pelo mínimo. A decisão está alinhada com os success criteria do roadmap para a Phase 2.

---

## Claude's Discretion

- `get_session()` async: usar `AsyncGenerator[AsyncSession, None]` como type hint — decisão técnica standard sem preferência expressa pelo usuário
- `create_db_and_tables()`: remover (Alembic gerencia o schema) — sem preferência expressa; capturado em D-05

## Deferred Ideas

- Campo `domain:` no YAML do DSL generator — Phase 3
- Output path `domains/{domain}/` no generator — Phase 3
- `GET /health` endpoint com ping ao banco — v2 requirements, milestone posterior
- SSL no `DATABASE_URL` em produção — Phase 5 deploy
