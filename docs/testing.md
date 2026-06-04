# Testes conduzidos pela IA

A IA assume integralmente os testes: escreve e atualiza os scripts conforme funcionalidades são implementadas, e executa os scripts ao verificar ou conduzir UAT. Só delega ao operador quando a automação é impossível (SSO com MFA, hardware externo).

---

## 1. Tipos de teste e quando usar cada um

| Tipo | O que cobre | Onde ficam | Quando executar |
|---|---|---|---|
| Unitário | Funções e componentes isolados | `tests/` ou `src/` do módulo | Ao alterar lógica interna de uma unidade |
| Integração de módulo | Fluxos internos de um módulo com dependências reais | `tests/` do módulo | Ao alterar fluxos ou contratos internos |
| E2E / UAT | Jornadas completas do usuário pela interface ou pela API | `e2e/` na raiz | Ao verificar funcionalidades ou conduzir UAT |

**UAT é sempre E2E** — testa o sistema em execução de ponta a ponta. Nunca substitua UAT por testes unitários.

---

## 2. Fluxo de UAT autônomo

### Passo 0 — verificar serviços em execução

Antes de qualquer setup, verificar se os serviços necessários já estão no ar conforme as URLs definidas em `docs/development.md` de cada módulo.

Se todos estiverem respondendo, pule direto para o Passo 3. Não suba serviços desnecessariamente.

### Passo 1 — preparar variáveis de ambiente (só se precisar subir serviços)

Verificar se o arquivo de variáveis de ambiente já existe **antes** de criar. Nunca sobrescreva um arquivo existente. Se ele existir e os serviços não estiverem no ar, investigar o motivo antes de subir.

### Passo 2 — subir os serviços (só se necessário)

Subir em background conforme `docs/development.md` de cada módulo. Aguardar o startup via health check antes de prosseguir.

### Passo 3 — executar os scripts E2E

Scripts E2E aceitam URLs via variável de ambiente com defaults apontando para localhost. Passe as variáveis na linha de comando se os defaults não servirem.

### Passo 4 — encerrar os serviços (só se foram subidos nesta sessão)

Se você subiu os serviços no Passo 2, encerre-os ao concluir. Não encerre processos que já estavam rodando antes do UAT.

---

## 3. Playwright

O CLI `playwright` está instalado globalmente. Usar diretamente — não via `npx`.

```bash
playwright screenshot --browser chromium http://localhost:3000 /tmp/page.png
```

Para scripts interativos, resolver o módulo Node a partir do CLI global:

```bash
PW_NM=$(dirname $(which playwright))/../lib/node_modules
node e2e/meu-script.js
```

Screenshots em `/tmp/` — descartados ao encerrar a sessão, usados para diagnóstico inline.

---

## 4. Scripts de teste

Scripts de integração entre módulos ficam em `e2e/` na raiz. Scripts de módulo único ficam em `tests/` do próprio módulo.

Ao implementar ou alterar funcionalidades, criar ou atualizar os scripts correspondentes.

Cada script em `e2e/` deve:

- ser autocontido e executável de forma independente
- listar os cenários cobertos em comentário no topo
- receber URLs base via variável de ambiente com defaults para localhost, nunca hardcoded

```
e2e/
  walking-skeleton.js   ← pilha completa end-to-end
  auth-flows.js         ← fluxos de autenticação e controle de acesso
```

---

*Agnóstico de stack — aplicável a qualquer monorepo com este padrão.*
