---
phase: 01-infra-base
reviewed: 2026-05-24T03:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - alembic/versions/20260524_0138_initial_schema.py
  - dsl/entities/user.yaml
  - .env.example
  - pyproject.toml
  - scripts/generate_code.py
  - src/caramello/core/config.py
  - src/caramello/database/session.py
  - src/caramello/main.py
  - src/caramello/models/familyinvitation.py
  - src/caramello/models/familymember.py
  - src/caramello/models/family.py
  - src/caramello/models/user.py
findings:
  critical: 7
  warning: 8
  info: 4
  total: 19
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-05-24T03:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

A infraestrutura base da Phase 1 cobre criação de schema via Alembic, modelos SQLModel gerados por DSL, routers CRUD gerados e configuração da aplicação FastAPI. O código funciona para o caminho feliz, mas contém problemas críticos de segurança e correção que impedem o envio para produção: ausência total de autenticação e autorização em todos os endpoints, vazamento de credencial de banco via `DATABASE_URL` exposta como atributo público no objeto `Settings`, um router de `FamilyMember` que expõe o modelo de tabela ORM diretamente (sem schema de leitura separado, e sem isolamento de chave primária interna), e inconsistências sérias entre o que o gerador de código produz e o que foi manualmente implementado no router de `FamilyMember`.

---

## Critical Issues

### CR-01: Nenhum endpoint possui autenticação ou autorização

**File:** `src/caramello/main.py:1-35` (afeta todos os routers)
**Issue:** Zero mecanismo de autenticação existe. Qualquer cliente anônimo na rede pode criar, listar, alterar e deletar usuários, famílias, convites e membros. O CLAUDE.md documenta explicitamente "No auth layer: Zero authentication or authorization exists" como gap arquitetural, mas isso precisa ser registrado como bloqueador antes de qualquer uso real. A constraint do projeto declara Keycloak com OIDC/JWT — a ausência de qualquer dependency de verificação de token significa que o backend não valida nenhum JWT emitido pelo Keycloak.
**Fix:** Implementar uma dependency FastAPI que valida o Bearer token JWT contra o JWKS do Keycloak (endpoint `/.well-known/openid-configuration`). Aplicar como dependency global no `app` ou em cada `include_router`. Sem isso, qualquer endpoint exposto é completamente público.

---

### CR-02: DB_PASSWORD exposto como atributo público no objeto settings

**File:** `src/caramello/core/config.py:22`
**Issue:** `DB_PASSWORD: str` é um atributo público da instância `settings` (singleton de módulo). Qualquer código que faça `from caramello.core.config import settings` pode acessar `settings.DB_PASSWORD` diretamente. Em logs de exceção não tratados, rastreamentos de pilha, ou endpoints que serializam o objeto `settings` por acidente, a senha do banco seria vazada. O objeto `Settings` também mantém `DATABASE_URL` como campo, que contém a senha embutida em texto plano após `model_post_init`.
**Fix:** Marcar `DB_PASSWORD` com `SecretStr` do Pydantic para que a senha seja mascarada em `repr()` e `str()`:
```python
from pydantic import SecretStr

DB_PASSWORD: SecretStr

# E na construção da URL:
password = f":{self.DB_PASSWORD.get_secret_value()}" if self.DB_PASSWORD else ""
```

---

### CR-03: Router de FamilyMember expõe modelo ORM diretamente e usa lookup por PK interna

**File:** `src/caramello/api/generated/familymember_router.py:11-27`
**Issue:** Três problemas críticos combinados neste arquivo:
1. `response_model=FamilyMember` (linha 11 e 18) expõe o modelo de tabela ORM diretamente, sem schema `FamilyMemberRead`. Campos internos (`user_id`, `family_id`) e qualquer campo sensível futuro são serializados sem filtro.
2. O endpoint `GET /{user_id}` (linha 22) usa `int` como parâmetro e faz `session.get(FamilyMember, user_id)` — isso usa a PK interna inteira, violando a convenção do projeto de usar `uuid` em URLs externas. Para link models sem `uuid`, a URL deveria receber ambas as chaves ou ser redesenhada.
3. `session.get(FamilyMember, user_id)` com uma única chave em uma tabela com PK composta (`user_id`, `family_id`) está errado: o SQLAlchemy/SQLModel espera uma tupla para PKs compostas. Passando apenas `user_id`, o resultado é indefinido — na melhor hipótese retorna o primeiro registro encontrado, na pior levanta exceção.
**Fix:**
```python
# Usar FamilyMemberRead como response_model
# Corrigir lookup com PK composta:
@router.get("/{user_id}/{family_id}", response_model=FamilyMemberRead)
def read_familymember(user_id: int, family_id: int, session: Session = Depends(get_session)):
    familymember = session.get(FamilyMember, (user_id, family_id))
    if not familymember:
        raise HTTPException(status_code=404, detail="FamilyMember not found")
    return familymember
```

---

### CR-04: FamilyInvitationCreate e FamilyMemberCreate aceitam IDs internos como input do cliente

**File:** `src/caramello/models/familyinvitation.py:32-37`, `src/caramello/models/familymember.py:25-30`
**Issue:** `FamilyInvitationCreate` exige `family_id: int` e `inviter_id: int` como campos de entrada. `FamilyMemberCreate` exige `user_id: int` e `family_id: int`. Esses são IDs internos sequenciais da tabela, nunca públicos segundo a convenção do projeto (APIs externas devem usar `uuid`). Qualquer cliente pode enumerar registros por força bruta usando IDs sequenciais, quebrando o isolamento entre famílias. Além disso, o router não valida se o `inviter_id` realmente corresponde ao usuário autenticado.
**Fix:** Os schemas `*Create` devem receber `uuid` da entidade relacionada (e.g., `family_uuid: UUID`, `inviter_uuid: UUID`). O router deve fazer o lookup pelo UUID para obter o `id` interno antes de persistir.

---

### CR-05: `generate_code.py` importa `settings` em tempo de módulo — causa falha de importação sem banco configurado

**File:** `scripts/generate_code.py:5`
**Issue:** `from caramello.core.config import settings` na linha 5 importa o singleton de configuração em tempo de módulo. Isso faz com que `settings = Settings()` seja executado, que por sua vez importa `session.py`, que cria o `engine` singleton (`create_engine(settings.DATABASE_URL)`). O script de geração de código não precisa de banco de dados — ele apenas lê YAMLs e escreve arquivos Python — mas falhará com `ValidationError` ou `OperationalError` se `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` ou `DB_NAME` não estiverem definidos no ambiente onde o script é executado (e.g., em CI/CD sem banco provisionado).
**Fix:** Remover o import de `settings` do script de geração. O script não usa `settings` em nenhum lugar do seu código.

---

### CR-06: `updated_at` nunca é atualizado automaticamente em operações PATCH

**File:** `src/caramello/api/generated/user_router.py:41-43` (e routers equivalentes para Family e FamilyInvitation)
**Issue:** No handler `update_*`, o loop `setattr(db_obj, key, value)` aplica apenas os campos enviados pelo cliente via `model_dump(exclude_unset=True)`. O campo `updated_at` tem `default_factory` (definido apenas na criação do objeto), mas não existe lógica de `on_update` em nenhum lugar. O campo DSL declara `on_update: now_utc` para `updated_at`, mas o gerador ignora completamente essa propriedade (ver `generate_code.py` linha 48 — `on_update` é lido do YAML mas nunca gerado em código). O resultado é que `updated_at` fica com o valor da criação para sempre.
**Fix:** No handler de PATCH, forçar a atualização do campo antes do commit:
```python
from datetime import datetime, timezone
db_obj.updated_at = datetime.now(timezone.utc)
session.add(db_obj)
session.commit()
```
Alternativamente, o gerador deve emitir um event listener SQLAlchemy `@event.listens_for` para `before_update`.

---

### CR-07: `generate_code.py` — a propriedade `on_update` do DSL é silenciosamente descartada

**File:** `scripts/generate_code.py:48`
**Issue:** O campo `on_update: now_utc` está definido na DSL de `user.yaml` (linha 48) para o campo `updated_at`. O parser do YAML lê essa propriedade mas a função `get_field_definition` nunca a emite — não há nenhuma referência à chave `on_update` em nenhum lugar de `generate_code.py`. O comportamento documentado na DSL não é implementado, criando uma discrepância silenciosa entre a especificação e o código gerado. Todos os modelos com `on_update` terão esse campo com semântica quebrada.
**Fix:** Em `get_field_definition`, detectar `on_update` e emitir um `sa_column_kwargs={"onupdate": ...}` ou gerar um listener SQLAlchemy:
```python
if field.get('on_update') == 'now_utc':
    field_args.append("sa_column_kwargs={'onupdate': lambda: datetime.now(timezone.utc)}")
```

---

## Warnings

### WR-01: DB_PASSWORD com valor `postgres` no .env.example normaliza senhas fracas

**File:** `.env.example:9`
**Issue:** `DB_PASSWORD=postgres` como valor de exemplo ensina implicitamente ao desenvolvedor que senhas simples são aceitáveis. Projetos tendem a copiar `.env.example` para `.env` sem alterar esses valores. Em ambientes Docker compose (documentados como estratégia de deploy), um PostgreSQL com senha `postgres` pode ficar acessível em rede interna com credencial trivial.
**Fix:** Substituir por um placeholder óbvio:
```
DB_PASSWORD=CHANGE_ME_strong_password_here
```

---

### WR-02: Variáveis do Keycloak vazias no .env.example sem documentação de onde obtê-las

**File:** `.env.example:17-19`
**Issue:** `KEYCLOAK_URL=`, `KEYCLOAK_REALM=` e `KEYCLOAK_CLIENT_ID=` estão presentes mas vazios, e não são lidos pelo `Settings` atual (`config.py` não declara essas variáveis). As variáveis existem no exemplo mas são ignoradas pelo sistema — são mortas. Quando a autenticação for implementada, um desenvolvedor pode supor que estas variáveis já estão sendo consumidas.
**Fix:** Ou remover as variáveis do `.env.example` até que sejam implementadas, ou adicionar um comentário explícito `# TODO: ainda não implementado` e incluí-las no `Settings` como `Optional[str] = None`.

---

### WR-03: `familymember_router.py` diverge do padrão gerado — foi escrito manualmente

**File:** `src/caramello/api/generated/familymember_router.py:1-27`
**Issue:** Este arquivo está no diretório `generated/` mas claramente não foi produzido pelo `generate_code.py`: usa `response_model=FamilyMember` (sem sufixo `Read`), não usa `FamilyMemberCreate`/`FamilyMemberUpdate`, não tem endpoints PATCH nem DELETE, e tem imports manuais adicionais (`datetime`). O contrato do projeto é que arquivos em `generated/` são sobrescritos a cada regeneração — qualquer edição manual será destruída na próxima geração. Se este arquivo é intencionalmente manual, deve ser movido para fora de `generated/`.
**Fix:** Mover para `src/caramello/api/` (fora de `generated/`) ou regenerar via DSL com os padrões corretos.

---

### WR-04: `FamilyMemberRead` expõe `user_id` e `family_id` (PKs internas) na resposta

**File:** `src/caramello/models/familymember.py:19-22`
**Issue:** O schema `FamilyMemberRead` inclui `user_id` e `family_id` como campos de saída. Segundo a convenção do projeto, APIs externas devem usar `uuid`, nunca `id`. Expor IDs sequenciais permite enumeração.
**Fix:** Redefinir `FamilyMemberRead` para expor identificadores via UUID dos objetos relacionados, ou pelo menos documentar que este é um link model e a exposição é intencional com justificativa explícita.

---

### WR-05: `FamilyMemberCreate` inclui `joined_at` como campo obrigatório de input

**File:** `src/caramello/models/familymember.py:25-30`
**Issue:** `joined_at: datetime` é obrigatório em `FamilyMemberCreate`. Este campo deveria ser preenchido automaticamente pelo sistema no momento da inserção (é um timestamp de auditoria), não informado pelo cliente. Um cliente malicioso pode enviar timestamps arbitrários para falsificar datas de adesão.
**Fix:** Remover `joined_at` de `FamilyMemberCreate` e definir como `default_factory=lambda: datetime.now(timezone.utc)` apenas no modelo de tabela.

---

### WR-06: `generate_code.py` — `base_fields` e `table_fields` são declarados mas nunca usados (dead code)

**File:** `scripts/generate_code.py:155-170`
**Issue:** As variáveis `base_fields` e `table_fields` são inicializadas como listas vazias e o loop `for f in fields` não popula nenhuma delas (apenas `pass`). Todo o bloco é código morto com comentários que descrevem uma arquitetura de geração mais sofisticada que nunca foi implementada. O código atual ignora completamente essa estrutura e usa uma estratégia mais simples abaixo.
**Fix:** Remover o bloco morto (linhas 155–170) para reduzir confusão sobre a arquitetura real do gerador.

---

### WR-07: `generate_router` usa variável nomeada `hero_data` — nome incorreto vazou de código-exemplo

**File:** `scripts/generate_code.py:301`
**Issue:** No template da função `update_*`, a variável local é nomeada `hero_data` — claramente copiada de um tutorial do SQLModel que usa uma entidade chamada `Hero`. Esse nome está nos routers gerados (ver `user_router.py:41`, `family_router.py:41`, `familyinvitation_router.py:41`). O código funciona, mas o nome errado é enganoso em revisão de código e indica que o template não foi auditado.
**Fix:** Renomear para `update_data` no template do gerador e regenerar os routers.

---

### WR-08: `pyproject.toml` define `dev` dependencies em dois grupos distintos e incompatíveis

**File:** `pyproject.toml:21-43`
**Issue:** Existem dois grupos de dependências de desenvolvimento declarados com a mesma chave `dev`, em seções diferentes: `[project.optional-dependencies] dev` (linha 21, apenas `datamodel-code-generator`) e `[dependency-groups] dev` (linha 38, com `httpx`, `pytest`, `ruff`, `mypy`). O `uv` trata `[dependency-groups]` como PEP 735, mas a duplicidade da chave `dev` pode causar comportamento inesperado dependendo da versão do `uv` e do comando usado para instalar. `datamodel-code-generator` pode não ser instalado quando se usa `uv sync --group dev`.
**Fix:** Consolidar tudo em `[dependency-groups] dev` (PEP 735, formato nativo do uv) e remover `[project.optional-dependencies]`.

---

## Info

### IN-01: Import `List` do `typing` obsoleto — usar built-in `list`

**File:** `src/caramello/models/user.py:1`, `src/caramello/models/family.py:1`, `src/caramello/models/familymember.py:1`, `src/caramello/models/familyinvitation.py:1`, `scripts/generate_code.py:4`
**Issue:** Todos os modelos importam `List` de `typing` mas o projeto configura `target-version = "py310"` no ruff. Em Python 3.9+, `list[T]` é o tipo built-in preferido. O ruff com regra `UP` (pyupgrade) deve sinalizar isso, mas os modelos gerados estão excluídos do lint (`ruff.exclude`).
**Fix:** No gerador, substituir `from typing import Optional, List` por `from typing import Optional` e usar `list[T]` diretamente nos tipos.

---

### IN-02: Imports não utilizados em todos os modelos gerados

**File:** `src/caramello/models/familymember.py:1-2`, `src/caramello/models/familyinvitation.py:1-2`, `src/caramello/models/family.py:1-2`
**Issue:** `List` (de `typing`) é importado em todos os arquivos de modelo mas nunca usado (os relacionamentos usam `list[...]` com letra minúscula). `EmailStr` é importado em `familymember.py` (linha 5) e `family.py` (linha 5) mas nenhum campo nesses modelos usa `EmailStr`. `UUID` e `uuid4` são importados em `familymember.py` mas não usados (o link model não tem campo UUID).
**Fix:** O gerador deve computar os imports necessários com base nos tipos realmente usados, em vez de emitir um conjunto fixo de imports.

---

### IN-03: Alembic revision ID não é um hexadecimal padrão

**File:** `alembic/versions/20260524_0138_initial_schema.py:21`
**Issue:** `revision: str = 'a1b2c3d4e5f6'` parece um valor de placeholder gerado manualmente, não um UUID/hash real produzido pelo Alembic. O Alembic gera IDs aleatórios de 12 hex chars por padrão — este valor é sequencial demais para ser aleatório. Se outra migration for gerada automaticamente pelo Alembic e este ID colidir ou criar ambiguidade no grafo de revisões, pode quebrar `alembic upgrade head`.
**Fix:** Verificar se o ID foi gerado pelo Alembic ou criado manualmente. Se manual, regenerar com `alembic revision` para garantir unicidade.

---

### IN-04: `create_db_and_tables()` em `session.py` nunca é chamada

**File:** `src/caramello/database/session.py:10-11`
**Issue:** A função `create_db_and_tables` existe mas não é chamada em nenhum lugar (nem em `main.py` em um evento `startup`, nem em nenhum script de setup). O projeto usa Alembic para migrations, então chamar `SQLModel.metadata.create_all` seria incorreto em produção, mas a função poderia confundir novos contribuidores que a chamem manualmente e acabem com schema inconsistente com o versionado pelo Alembic.
**Fix:** Ou remover a função, ou adicionar um comentário explícito documentando que ela é apenas para testes unitários com banco in-memory e nunca deve ser usada em produção/desenvolvimento.

---

_Reviewed: 2026-05-24T03:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
