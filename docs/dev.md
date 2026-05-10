# Desenvolvimento local

> **Em construção.** Este documento está sendo expandido para cobrir o fluxo completo deste projeto.

Este documento cobre setup e operações do dia a dia de desenvolvimento do `caramello-api`.

Para runtime empacotado via Docker, use `docs/deploy.md`. Para fechar uma release, use `docs/release.md`.

## Pré-requisitos

- **Python 3.10+**
- **uv** — gerenciador de pacotes: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **PostgreSQL** rodando localmente (obrigatório — SQLite não é suportado)

## 1. Instalação

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## 2. Configuração

```bash
cp .env.example .env
```

Edite `.env` com as credenciais do seu banco PostgreSQL local. O `.env` nunca deve ser commitado.

## 3. Banco de dados

Crie o usuário e banco definidos no `.env` (requer superusuário do Postgres):

```bash
./bin/setup_db
```

Aplique as migrações:

```bash
./bin/manage_db init
```

## 4. Rodar a aplicação

```bash
uv run uvicorn caramello.main:app --reload
```

O servidor sobe em `http://localhost:8000`.

## 5. Rodar os testes

```bash
uv run pytest
```

## 6. Fluxo DSL → código → banco

O projeto usa DSL em YAML como fonte de verdade. O fluxo completo:

```bash
# 1. Editar definições em dsl/
# 2. Gerar models e routers
./bin/generate_code

# 3. Criar migração a partir dos models gerados
alembic revision --autogenerate -m "descricao"

# 4. Aplicar migração
./bin/manage_db upgrade

# 5. Verificar consistência
./bin/validate_generation
```

## 7. Comandos de banco úteis

| Comando | Descrição |
| :--- | :--- |
| `./bin/manage_db init` | Aplica todas as migrações pendentes |
| `./bin/manage_db migrate "desc"` | Gera nova migração |
| `./bin/manage_db reset` | **CUIDADO:** apaga todos os dados e recria |
