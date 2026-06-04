---
phase: 05-mcp-testes-e-docker
reviewed: 2026-05-27T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - compose.yaml
  - Dockerfile
  - .dockerignore
  - pyproject.toml
  - src/caramello/families/operations.py
  - src/caramello/families/services.py
  - src/caramello/main.py
  - tests/conftest.py
  - tests/test_api/test_families_integration.py
  - tests/test_api/test_mcp.py
  - tests/test_api/test_version.py
  - tests/test_services/test_family_service.py
findings:
  critical: 4
  warning: 5
  info: 3
  total: 12
status: issues_found
---

# Phase 5: Code Review Report

**Revisado:** 2026-05-27
**Profundidade:** standard
**Arquivos revisados:** 12
**Status:** issues_found

## Resumo

A implementação cobre Docker/compose, MCP, testes unitários e de integração para o domínio `families`. A estrutura geral está correta e os padrões de service/operations foram aplicados consistentemente. No entanto, foram identificados quatro problemas bloqueadores: dois bugs de correção de comportamento (auto-join processa apenas a primeira convite pendente, e o owner pode se auto-remover deixando a família sem dono), um problema de segurança de autenticação (JWT audience desabilitado sem plano de ativação), e um bug de construção de URL que pode corromper a conexão ao banco quando `DB_PASSWORD` contém caracteres especiais. Há também cinco warnings relevantes de qualidade e robustez.

---

## Critical Issues

### CR-01: Auto-join processa apenas o primeiro convite pendente de um email

**Arquivo:** `src/caramello/shared/auth.py:213`

**Problema:** A query de auto-join usa `.first()` ao invés de `.all()`. Se um email foi pré-registrado em múltiplas famílias antes do primeiro login, somente a primeira `FamilyInvitation` encontrada (ordem não determinística da query) será processada. As demais permanecem como `"pending_login"` para sempre, e o usuário nunca é adicionado às outras famílias — comportamento silenciosamente incorreto, sem erro visível.

```python
# auth.py linha 213 — busca apenas o primeiro
pending_inv = inv_result.first()
if pending_inv is not None:
    ...
    pending_inv.status = "joined"
```

**Correção:**

```python
pending_invs = inv_result.all()
for pending_inv in pending_invs:
    # verificar se já é membro antes de inserir
    existing = await session.exec(
        select(FamilyMember).where(
            FamilyMember.user_id == user.id,
            FamilyMember.family_id == pending_inv.family_id,
        )
    )
    if existing.first() is None:
        new_member = FamilyMember(
            user_id=user.id,
            family_id=pending_inv.family_id,
            role="member",
        )
        session.add(new_member)
    pending_inv.status = "joined"
    session.add(pending_inv)
await session.commit()
```

---

### CR-02: Owner pode se auto-remover, deixando a família órfã

**Arquivo:** `src/caramello/families/operations.py:258-294`

**Problema:** O endpoint `DELETE /families/{family_uuid}/members/{user_uuid}` não impede que o owner remova seu próprio `user_uuid`. Um owner que se auto-remove deixa a família sem nenhum owner. Qualquer outro membro existente perde acesso às operações que requerem `_require_owner`, e não há mecanismo para promover outro membro. A família fica em estado irrecuperável via API.

```python
# Não há verificação:
# if target_user.id == current_user.id:
#     raise HTTPException(400, "Owner não pode se auto-remover")
await session.delete(target_member)
await session.commit()
```

**Correção:**

```python
# Inserir antes de deletar o membership
if target_user.id == current_user.id:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Owner não pode remover a si mesmo da família",
    )
```

---

### CR-03: JWT audience verification desabilitada sem plano de ativação

**Arquivo:** `src/caramello/shared/auth.py:154-156`

**Problema:** `verify_aud=False` desabilita a verificação da claim `aud` do JWT. Qualquer token emitido pelo Keycloak configurado (para qualquer client/aplicação do mesmo realm) será aceito como válido na API. Um token destinado ao frontend, a outro serviço ou ao admin console do próprio Keycloak pode ser usado para autenticar na API. Isso viola o princípio de least-privilege de audience e abre brecha para token confusion entre serviços do mesmo realm.

```python
options={"verify_aud": False},
# D-02: começar com verify_aud=False; ativar após inspecionar token real
```

O comentário menciona "uma task de inspeção de token real (Plan 05) decide quando ativar" — porém essa task não está presente nos arquivos desta phase, e o código segue para produção com a verificação desabilitada.

**Correção:**

```python
# Verificar qual audience o Keycloak popula no token (claim 'aud' ou 'azp')
# e ativar a verificação antes de ir para produção:
payload = jwt.decode(
    token,
    public_key,
    algorithms=["RS256"],
    audience=settings.KEYCLOAK_CLIENT_ID,  # ou valor correto da claim aud
)
```

Se o Keycloak popular `azp` em vez de `aud`, a verificação pode ser feita manualmente após o decode sobre `payload.get("azp")`.

---

### CR-04: DB_PASSWORD com caracteres especiais corrompe a DATABASE_URL

**Arquivo:** `src/caramello/core/config.py:37-41`

**Problema:** A construção da `DATABASE_URL` interpola `DB_PASSWORD` diretamente na string sem encoding de URL. Se a senha contiver `@`, `:`, `/`, `?` ou `#` (todos válidos em senhas PostgreSQL), a URL fica malformada e o asyncpg falha ao parsear o host. Por exemplo, `DB_PASSWORD=secret@prod` produz `postgresql+asyncpg://user:secret@prod@host:5432/db`, que faz o asyncpg interpretar `prod` como o host.

```python
# config.py linhas 37-41
password = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
self.DATABASE_URL = (
    f"postgresql+asyncpg://{self.DB_USER}{password}@{self.DB_HOST}{port}/{self.DB_NAME}"
)
```

**Correção:**

```python
from urllib.parse import quote_plus

password = f":{quote_plus(self.DB_PASSWORD)}" if self.DB_PASSWORD else ""
user = quote_plus(self.DB_USER)
self.DATABASE_URL = (
    f"postgresql+asyncpg://{user}{password}@{self.DB_HOST}{port}/{self.DB_NAME}"
)
```

---

## Warnings

### WR-01: Auto-join não verifica FamilyMember duplicado antes de inserir

**Arquivo:** `src/caramello/shared/auth.py:214-223`

**Problema:** O código de auto-join cria um `FamilyMember` sem verificar se o usuário já é membro da família. Se o mesmo usuário fizer dois requests simultâneos no primeiro login, ambos poderão passar pela verificação `pending_inv is not None` e tentar inserir o mesmo `(user_id, family_id)` na tabela `family_member` (composite PK). Isso resultará em `IntegrityError` para o segundo request, retornando 500 em vez de 200.

**Correção:** Adicionar `on_conflict_do_nothing` na inserção de `FamilyMember`, ou verificar existência antes de inserir (conforme exemplo em CR-01).

---

### WR-02: CORS_ORIGINS com env_ignore_empty cai silenciosamente para origens de desenvolvimento

**Arquivo:** `src/caramello/core/config.py:26` + `compose.yaml:17`

**Problema:** `env_ignore_empty=True` faz com que `CORS_ORIGINS=""` (string vazia) seja ignorado pelo pydantic-settings, e o valor efetivo cai no default `["http://localhost:3000", "http://localhost:5173"]`. O `compose.yaml` define `CORS_ORIGINS: ${CORS_ORIGINS:-}`, que resulta em string vazia quando a variável não está no `.env` de produção. Resultado: em produção sem `CORS_ORIGINS` configurado, o servidor aceita requests com origin de localhost do desenvolvedor — comportamento contrário ao esperado.

**Correção:** Tornar `CORS_ORIGINS` obrigatório em ambiente de produção, ou remover o default de localhost:

```python
# Opção 1: sem default (campo obrigatório)
CORS_ORIGINS: list[str]

# Opção 2: default vazio (nenhuma origin permitida sem configuração explícita)
CORS_ORIGINS: list[str] = []
```

---

### WR-03: `test_engine` com scope="session" e `db_session` com scope="function" causam incompatibilidade com event loop no pytest-asyncio

**Arquivo:** `tests/conftest.py:33-53`

**Problema:** `test_engine` é declarado como `scope="session"` mas `db_session` (que depende de `test_engine`) é `scope="function"` (padrão). Com `asyncio_mode = "auto"` no pytest-asyncio 1.x, fixtures de session scope precisam de `loop_scope="session"` ou de um event loop compartilhado. Sem isso, o engine criado no event loop da sessão pode ser usado em um event loop diferente a cada teste, causando `RuntimeError: Task attached to a different loop` em execuções paralelas ou após o primeiro teste fechar o loop.

**Correção:**

```python
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    ...
```

E adicionar no `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
```

---

### WR-04: `FamilyInvitationRead` expõe IDs internos (`family_id`, `inviter_id`)

**Arquivo:** `src/caramello/families/models.py:92-98`

**Problema:** O schema `FamilyInvitationRead` expõe `family_id: int` e `inviter_id: int`, que são PKs internas sequenciais. A convenção do projeto (CLAUDE.md, seção Naming) é que "External URLs and API responses use `uuid`, never `id`." Os IDs internos permitem enumeração de recursos e facilitam ataques de reconhecimento.

```python
class FamilyInvitationRead(SQLModel):
    uuid: UUID
    family_id: int    # deveria ser family_uuid: UUID
    inviter_id: int   # deveria ser inviter_uuid: UUID
    ...
```

**Correção:** Substituir `family_id: int` por `family_uuid: UUID` e `inviter_id: int` por `inviter_uuid: UUID`, com resolução via JOIN na camada de operação.

---

### WR-05: Ausência de proteção contra convite duplicado (mesmo email, mesma família)

**Arquivo:** `src/caramello/families/operations.py:207-217`

**Problema:** O endpoint `POST /families/{uuid}/pre-register` não verifica se já existe uma `FamilyInvitation` com `status="pending_login"` para o mesmo `(email, family_id)`. Um owner pode chamar o endpoint múltiplas vezes com o mesmo email e criar N invitations idênticas. Quando o usuário fizer login, apenas a primeira será processada (ver CR-01), e as demais ficarão presas como `"pending_login"` para sempre. Não há `UniqueConstraint` na tabela para impedir isso a nível de banco.

**Correção:**

```python
# Verificar existência antes de inserir
existing = await session.exec(
    select(FamilyInvitation).where(
        FamilyInvitation.family_id == family.id,
        FamilyInvitation.email == str(body.email),
        FamilyInvitation.status == "pending_login",
    )
)
if existing.first() is not None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Email já foi pré-registrado nesta família",
    )
```

Adicionalmente, considerar um `UniqueConstraint` em `(family_id, email)` para `status != "joined"`.

---

## Info

### IN-01: `@pytest.mark.asyncio` redundante com `asyncio_mode = "auto"`

**Arquivo:** `tests/test_services/test_family_service.py:43,69,87`

**Problema:** Com `asyncio_mode = "auto"` configurado no `pyproject.toml`, o decorator `@pytest.mark.asyncio` é desnecessário em todas as funções async de teste. Não causa falha, mas adiciona ruído e pode confundir ao sugerir que a anotação é obrigatória.

**Correção:** Remover os decorators `@pytest.mark.asyncio` dos três testes.

---

### IN-02: `packages` declarado fora de `[tool.setuptools]` no `pyproject.toml`

**Arquivo:** `pyproject.toml:35`

**Problema:** A linha `packages = [{ include = "caramello", from = "src" }]` está no nível raiz do `pyproject.toml`, fora de qualquer seção. Ela deveria estar em `[tool.setuptools.packages.find]` ou `[tool.setuptools]` para ser reconhecida pelo setuptools. Atualmente pode estar sendo ignorada silenciosamente, com o setuptools descobrindo pacotes por auto-discovery (que pode incluir ou excluir incorretamente).

**Correção:**

```toml
[tool.setuptools.packages.find]
where = ["src"]
```

---

### IN-03: `test_mcp_with_valid_token_returns_tools` não verifica ferramentas MCP na resposta

**Arquivo:** `tests/test_api/test_mcp.py:21-66`

**Problema:** O teste verifica que `/mcp` retorna 200 com `jsonrpc: "2.0"` e campo `result`, mas não verifica que as ferramentas MCP esperadas (`list_my_families`) estão presentes. O objetivo declarado no docstring é "retorna estrutura MCP válida com ferramentas", mas a asserção é apenas estrutural — um `initialize` vazio satisfaz o teste mesmo que nenhuma tool seja registrada.

**Correção:** Após o `initialize`, fazer um segundo request com `tools/list` e verificar:

```python
tools_response = client.post(
    "/mcp",
    json={"jsonrpc": "2.0", "method": "tools/list", "id": 2},
    headers={...},
)
tools_data = tools_response.json()
tool_names = [t["name"] for t in tools_data["result"]["tools"]]
assert "list_my_families" in tool_names
```

---

_Revisado em: 2026-05-27_
_Revisor: Claude (gsd-code-reviewer)_
_Profundidade: standard_
