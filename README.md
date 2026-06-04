# Caramello

Plataforma pessoal e familiar para centralizar agenda, finanças, listas de compras, saúde e entretenimento. Destinada a um grupo fechado de 1 a 5 usuários (membros da família), com autenticação via Keycloak e acesso por aplicações web/mobile e agentes de IA.

---

## Módulos

| Módulo | Descrição |
|---|---|
| [`apps/backend`](apps/backend/README.md) | API Python/FastAPI — núcleo de dados e regras de negócio |
| [`apps/frontend`](apps/frontend/README.md) | Aplicativo mobile-first React/Capacitor — em definição |

---

## Documentação transversal

- [`docs/monorepo.md`](docs/monorepo.md) — convenções de organização, escopo e documentação do monorepo
- [`docs/testing.md`](docs/testing.md) — estratégia de testes conduzidos pela IA e UAT E2E
