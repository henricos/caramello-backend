# Phase 5: MCP, Testes e Docker - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 05-mcp-testes-e-docker
**Areas discussed:** Escopo das ferramentas MCP, Banco de testes e isolamento, Docker compose para desenvolvimento

---

## Escopo das Ferramentas MCP

| Option | Description | Selected |
|--------|-------------|----------|
| Por tags FastAPI | Criar tags 'MCP' ou 'MCP-Read' nos routers, fastapi-mcp inclui só esses | |
| Lista manual de rotas | Passar lista explícita de caminhos para o fastapi-mcp | |
| Prefixo de include separado | Sub-app separado montado no fastapi-mcp | |
| Expor tudo (sem filtro) | fastapi-mcp exibe todos os endpoints automaticamente | |

**User's choice:** Freeform — "ainda precisamos discutir melhor a parte de MCP. acho que serão pouco os casos onde o mesmo endpoint vai ser exposto com a mesma assinatura como MCP. o que eu preciso e quero reaproveitar é o service. entao talvez os mcps devam ser implementados na mão e não gerados. talvez eu precise gerar apenas 1 ou 2 para ter o exemplo."

**Notes:** O usuário identificou que a assinatura REST ≠ assinatura MCP — reutilização é via services, não via exposição de routers. fastapi-mcp serve apenas como runtime/servidor MCP, não como gerador automático de ferramentas.

---

## Modelo de Implementação MCP

| Option | Description | Selected |
|--------|-------------|----------|
| MCP manual sobre services | tools.py chama services.py dos domínios | ✓ |
| MCP como router FastAPI separado | Router dedicado /mcp-tools/... | |
| Só prototipar | servidor vazio + 1 exemplo superficial | |

**User's choice:** MCP manual sobre services

---

## Ferramentas MCP na Phase 5

| Option | Description | Selected |
|--------|-------------|----------|
| Apenas ferramentas de leitura | get_my_families, get_family_details, get_family_members, get_my_profile | |
| Leitura + escrita essencial | + create_family, pre_register_member | |
| Somente 1 ferramenta de exemplo | Apenas get_my_families — prova de conceito | ✓ |

**User's choice:** Somente 1 ferramenta de exemplo (`get_my_families`)

---

## Banco de Testes — Estratégia

| Option | Description | Selected |
|--------|-------------|----------|
| Banco real familia_test | PostgreSQL real, fixtures, rollback | |
| Continuar com AsyncMock | Sem PG necessário, mais rápido | |

**User's choice:** Freeform — "eu tenho banco real para dev diferente do banco de produção mas preciso de scripts facilitadores para recriar /zerar todo o banco para rodar migration do zero sempre que quiser"

**Notes:** Confirmou banco real. Revelou divergência de nomenclatura — bancos reais se chamam `caramello` (prod) e `caramello_dev` (dev), não `familia_prod`/`familia_dev` como documentado. Banco de testes será `caramello_test`.

---

## Nomenclatura de Banco

| Option | Description | Selected |
|--------|-------------|----------|
| Atualizar docs para refletir o real | caramello / caramello_dev / caramello_test | ✓ |
| Renomear bancos para familia_dev / familia_prod | Alinhar realidade com documentação | |

**User's choice:** Atualizar docs

---

## Estratégia de Isolamento de Testes

| Option | Description | Selected |
|--------|-------------|----------|
| Transaction rollback por teste | Mais rápido, sempre limpo | ✓ |
| Truncate de tabelas por teste | Mais simples, mais lento | |
| Banco limpo por sessão | Mais rápido, menos isolado | |

**User's choice:** Transaction rollback por teste

---

## Gerenciamento do Banco de Testes

| Option | Description | Selected |
|--------|-------------|----------|
| bin/manage_db --env test | Integra no script existente | ✓ |
| bin/setup_test_db dedicado | Script novo, responsabilidades separadas | |
| Fixture automática no pytest | Zero intervenção manual | |

**User's choice:** bin/manage_db --env test (após explicação detalhada das opções)

---

## Coexistência de Testes Unit + Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Coexistem com marcação @pytest.mark.integration | uv run pytest -m 'not integration' funciona sem PG | ✓ |
| Migrar todos para banco real | Mais consistente, requer PG em todo ambiente | |

**User's choice:** Coexistem com marcação

---

## Docker Compose para Desenvolvimento

| Option | Description | Selected |
|--------|-------------|----------|
| Apenas compose.yaml de produção (app only) | PG externo, sem compose para dev | ✓ |
| compose.yaml + compose.override para dev | Adiciona PG via override | |
| Dois compose separados | compose.yaml (prod) + docker-compose.dev.yml | |

**User's choice:** Apenas compose.yaml de produção (app only)

---

## APP_VERSION na OpenAPI Spec

| Option | Description | Selected |
|--------|-------------|----------|
| No campo version da OpenAPI | FastAPI(version=...) | ✓ |
| No título da spec | FastAPI(title=f'Caramello API v{VERSION}') | |
| Em endpoint de health separado | GET /health retorna version | |

**User's choice:** No campo version da OpenAPI

---

## Claude's Discretion

Nenhuma área foi delegada inteiramente ao Claude — todas as decisões foram tomadas pelo operador.

## Deferred Ideas

- Ferramentas MCP de escrita (M2+): create_family, pre_register_member
- Ferramentas MCP adicionais de leitura (M2+): get_family_details, get_family_members, get_my_profile
- `GET /health` com ping ao banco (OPS-01 v2)
- CI pipeline GitHub Actions (OPS-04 v2)
- Docker compose com PostgreSQL incluso para dev (compose.override.yml futuramente)
