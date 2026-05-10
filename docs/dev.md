# Desenvolvimento local

> **Em construção.** Este documento está sendo expandido para cobrir o fluxo completo deste projeto.

Este documento cobre setup e operações do dia a dia de desenvolvimento do `caramello-api`.

Para runtime empacotado via Docker, use `docs/deploy.md`. Para fechar uma release, use `docs/release.md`.

## Pré-requisitos

- **Python 3.10+**
- **uv** - gerenciador de pacotes:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **PostgreSQL** rodando localmente (obrigatório - SQLite não é suportado)

## 1. Instalação

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
uv pip install -e ".[dev]"
```

## 2. Configuração

```bash
cp .env.example .env
```

Edite `.env` com as credenciais do seu banco PostgreSQL local. O `.env` nunca deve ser commitado.

### Variáveis obrigatórias

| Variável | Descrição | Padrão |
| :--- | :--- | :--- |
| `ENVIRONMENT` | Ambiente de execução (`development`, `qa`, `production`) | `development` |
| `DB_HOST` | Host do banco de dados | `localhost` |
| `DB_PORT` | Porta do banco de dados | `5432` |
| `DB_USER` | Usuário do banco de dados | `postgres` |
| `DB_PASSWORD` | Senha do banco de dados | `postgres` |
| `DB_NAME` | Nome do banco de dados | `caramello_db` |

## 3. Banco de dados

Crie o usuário e banco definidos no `.env` (requer superusuário do Postgres):

```bash
./bin/setup_db
```

O script irá:
1. Ler `DB_USER` e `DB_NAME` do `.env`.
2. Verificar se o banco já existe.
3. Se existir, oferecer o modo **RESET** (drop & create) para começar do zero.
4. Se não existir, criar o usuário (role) e o banco com as permissões corretas.

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
