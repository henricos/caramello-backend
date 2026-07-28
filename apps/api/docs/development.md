# Desenvolvimento — Backend

Setup, comandos e operações do dia a dia para o módulo `apps/backend`.

Para deploy em produção via Docker, veja `docs/deploy.md`. Para fechar uma release, veja `docs/release.md`.

---

## Pré-requisitos

- **Python 3.10+**
- **uv** (gerenciador de pacotes):
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **PostgreSQL** rodando localmente — SQLite não é suportado

---

## Instalação

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
uv pip install -e ".[dev]"
```

---

## Variáveis de ambiente

```bash
cp .env.example .env
```

Edite `.env` com as credenciais do seu banco local. O arquivo nunca deve ser commitado.

| Variável | Descrição | Padrão |
|---|---|---|
| `ENVIRONMENT` | Ambiente (`development`, `qa`, `production`) | `development` |
| `DB_HOST` | Host do banco | `localhost` |
| `DB_PORT` | Porta do banco | `5432` |
| `DB_USER` | Usuário do banco | `postgres` |
| `DB_PASSWORD` | Senha do banco | `postgres` |
| `DB_NAME` | Nome do banco | `caramello_db` |

Convenção de nomes: `caramello` (prod), `caramello_dev` (dev).

---

## Banco de dados

Crie o usuário e banco definidos no `.env`:

```bash
./bin/setup_db
```

Aplique as migrações:

```bash
./bin/manage_db init
```

---

## Rodar a aplicação

```bash
uv run uvicorn caramello.main:app --reload
```

Sobe em `http://localhost:8000`. Documentação interativa em `http://localhost:8000/docs`.

---

## Testes

```bash
uv run pytest
```

---

## Fluxo DSL → código → banco

O DSL em `dsl/` é a fonte de verdade. Sempre siga este fluxo ao criar ou alterar entidades:

```bash
# 1. Editar definições em dsl/entities/ ou dsl/operations/

# 2. Gerar models, routers e stubs
./bin/generate_code

# 3. Implementar stubs gerados (se houver operações novas)

# 4. Criar migração a partir dos models gerados
alembic revision --autogenerate -m "descricao"

# 5. Aplicar migração
./bin/manage_db upgrade

# 6. Verificar consistência
./bin/validate_generation
```

---

## Comandos de banco

| Comando | Descrição |
|---|---|
| `./bin/manage_db init` | Aplica todas as migrações pendentes |
| `./bin/manage_db migrate "desc"` | Gera nova migração |
| `./bin/manage_db reset` | **CUIDADO:** apaga todos os dados e recria o schema |

---

## Estrutura de pastas

```
apps/backend/
  alembic/          migrações de banco
  bin/              scripts utilitários (setup_db, manage_db, generate_code)
  docs/             documentação técnica do módulo
  dsl/
    entities/       definições YAML de entidades (fonte de verdade)
    operations/     definições YAML de endpoints de negócio
  scripts/          scripts auxiliares de geração
  src/caramello/
    api/            routers FastAPI
    core/           configurações e utilitários globais
    database/       sessão e engine
    domains/        módulos de domínio (models, router, operations, services)
  tests/            testes automatizados
```
