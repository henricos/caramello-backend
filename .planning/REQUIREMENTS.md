# Requirements: Caramello API — Milestone 2: Domínio Financeiro

**Definido:** 2026-05-30
**Core Value:** Um backend sólido, seguro e extensível onde cada novo domínio de negócio pode ser adicionado sem tocar no que já existe.

---

## Glossário do Domínio

| Termo | Conceito |
|-------|---------|
| **Conta** | Conta bancária, cartão, poupança ou investimento de um membro da família |
| **Movimentação** | Fato bancário bruto — crédito ou débito com data, valor e descrição; imutável |
| **Lançamento financeiro** | Movimentação conciliada com significado: categoria (2 níveis) + competência (ano/mês) + campos analíticos; base de todos os relatórios |
| **Categoria** | Hierarquia 2 níveis (Transporte > Gasolina) scoped por família |
| **Competência** | Período contábil (ano/mês) do lançamento financeiro, pode diferir da data da movimentação |
| **Conciliação** | Ato de transformar uma movimentação bruta em um lançamento financeiro classificado |

---

## v2 Requirements

### Contas

- [x] **ACC-01**: Usuário autenticado pode criar conta para sua família (nome, tipo: corrente/poupança/cartão/investimento, moeda)
- [x] **ACC-02**: Usuário pode listar, detalhar e atualizar contas da família
- [x] **ACC-03**: Usuário pode arquivar conta (`is_active=false`) sem perder histórico de movimentações

### Categorias

- [x] **CAT-01**: Usuário pode criar categoria de nível 1 (pai) para a família
- [x] **CAT-02**: Usuário pode criar subcategoria de nível 2 vinculada a uma categoria pai
- [x] **CAT-03**: Sistema rejeita criação de subcategoria filha de subcategoria — máximo 2 níveis
- [x] **CAT-04**: Usuário pode listar e atualizar categorias da família

### Movimentações

- [ ] **MOV-01**: Usuário pode registrar movimentação individual em uma conta (tipo crédito/débito, data, valor, descrição)
- [ ] **MOV-02**: Usuário pode importar movimentações em lote via arquivo CSV
- [ ] **MOV-03**: Usuário pode importar movimentações em lote via arquivo OFX ou XLSX
- [ ] **MOV-04**: Importação em lote detecta duplicatas via hash — reimportar o mesmo arquivo não cria entradas duplicadas
- [ ] **MOV-05**: Movimentações detectadas como duplicatas são marcadas (`is_duplicate=true`) em vez de rejeitadas, permitindo revisão posterior

### Lançamentos Financeiros (Conciliação)

- [x] **LAN-01**: Usuário pode conciliar uma movimentação criando um lançamento financeiro (subcategoria, competência ano/mês, notas)
- [x] **LAN-02**: Uma movimentação só pode ter um lançamento financeiro (1:1) — tentativa de duplicar retorna 409
- [x] **LAN-03**: Sistema propõe subcategoria baseado em similaridade de descrição com lançamentos anteriores (semi-automático, usuário confirma)
- [x] **LAN-04**: Usuário pode marcar lançamento financeiro como recorrente (sem geração automática neste milestone)
- [x] **LAN-05**: Usuário pode atualizar subcategoria e competência de lançamento financeiro existente

### Relatórios e Saldos

- [x] **REL-01**: Usuário pode consultar saldo atual de uma conta (soma créditos − débitos de movimentações)
- [x] **REL-02**: Usuário pode consultar saldo consolidado de todas as contas da família
- [x] **REL-03**: Usuário pode consultar breakdown mensal por categoria pai (total de lançamentos financeiros por competência agrupado por nível 1)
- [x] **REL-04**: Usuário pode detalhar breakdown por subcategoria dentro de uma categoria pai e competência
- [x] **REL-05**: Todos os relatórios analíticos operam sobre lançamentos financeiros e filtram por competência, não por data da movimentação

### Autorização

- [x] **AUTH-FIN-01**: Todos os endpoints do domínio finances exigem Bearer token válido (401 sem token)
- [x] **AUTH-FIN-02**: Usuário só acessa contas, movimentações e lançamentos de famílias das quais é membro (403 caso contrário)

---

## Fora do Escopo do M2

| Feature | Razão |
|---------|-------|
| Geração automática de recorrências | Marca-se como recorrente; auto-geração vem no M3 |
| Outros membros registrando movimentações | M2 foco no owner; permissões granulares no M3 |
| Ciclos de fatura automáticos por conta | Complexidade desnecessária no M2 |
| Splits de movimentação (1:N) | Conciliação 1:1 suficiente para o M2 |
| Budget/forecast/metas | Domínio separado, milestone futuro |
| Open Banking / feeds automáticos | Escala e compliance desnecessários para 1-5 usuários |
| FAMILY-04/05/06 (convites reutilizáveis) | Deferido do M1 — incluir no M3 |

---

## Requisitos Técnicos (não funcionais)

- **Precisão monetária**: `NUMERIC(15,2)` no banco + `Decimal` no Python — nenhum `float` em campo de valor
- **Deduplicação**: hash SHA-256 de `(account_id, date, amount, normalized_description)` como coluna `UNIQUE`
- **Agregações**: `session.execute()` com `func.sum + group_by` — não `session.exec()`
- **Importação**: CSV (stdlib), OFX (`ofxparse`), XLSX (`openpyxl`) — sem pandas
- **Sugestão de categoria**: `rapidfuzz.token_set_ratio` contra histórico de lançamentos

---

## Traceability

| Requisito | Fase | Status |
|-----------|------|--------|
| ACC-01 | Phase 7 | Complete |
| ACC-02 | Phase 7 | Complete |
| ACC-03 | Phase 7 | Complete |
| CAT-01 | Phase 7 | Complete |
| CAT-02 | Phase 7 | Complete |
| CAT-03 | Phase 7 | Complete |
| CAT-04 | Phase 7 | Complete |
| AUTH-FIN-01 | Phase 7 | Complete |
| AUTH-FIN-02 | Phase 7 | Complete |
| MOV-01 | Phase 8 | Pending |
| MOV-02 | Phase 8 | Pending |
| MOV-03 | Phase 8 | Pending |
| MOV-04 | Phase 8 | Pending |
| MOV-05 | Phase 8 | Pending |
| LAN-01 | Phase 9 | Complete |
| LAN-02 | Phase 9 | Complete |
| LAN-03 | Phase 9 | Complete |
| LAN-04 | Phase 9 | Complete |
| LAN-05 | Phase 9 | Complete |
| REL-01 | Phase 9 | Complete |
| REL-02 | Phase 9 | Complete |
| REL-03 | Phase 9 | Complete |
| REL-04 | Phase 9 | Complete |
| REL-05 | Phase 9 | Complete |

**Cobertura:** 24 requisitos · 24 mapeados · 0 fora do escopo

---

*Requirements definidos: 2026-05-30*
