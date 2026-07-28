# Plataforma Pessoal — Contexto, Decisões e Arquitetura

---

## Visão Geral

Conjunto de aplicações web pessoais independentes, rodando em servidor próprio via Docker com DNS público. O objetivo atual é experimentação e evolução incremental, com convergência futura para agrupamentos lógicos por domínio de uso. O volume de uso é pequeno (1 a 5 usuários). Performance não é prioridade; simplicidade, flexibilidade, manutenibilidade e evolução gradual são.

---

## 1. Universo de Aplicações

Total estimado: **10 a 15 aplicações**, organizadas em três grupos com perfis distintos de arquitetura e convergência.

### Grupo A — Família
- Aplicações de gestão familiar: orçamento, lista de compras, compromissos familiares e similares.
- Usuários: conjunto fechado e conhecido (membros da família).
- Domínio coeso — as funcionalidades se beneficiam de dados compartilhados entre si.
- **Destino definido:** backend monolítico único com APIs organizadas por domínio de negócio. Frontend único, mobile-first, crescendo gradualmente com novas funcionalidades adicionadas ao menu. Empacotado como aplicativo mobile via Capacitor.

### Grupo B — Trabalho
- Aplicações de produtividade profissional: gestão de atividades, geração de apresentações, registro de feedback de equipe, base de conhecimento, estudos e similares.
- Usuários: predominantemente um único usuário, com porta aberta para eventual compartilhamento com um segundo usuário no futuro.
- **Requisito de UX:** isolamento de contexto visual — interfaces de assuntos distintos não devem ser misturadas na mesma tela, inclusive porque algumas dessas interfaces são usadas no dia a dia profissional.
- **Modelo de navegação desejado:** chaveamento tipo Google (Gmail/YouTube) — SSO compartilhado com menu de atalho entre as aplicações, mas cada uma abre sua própria interface limpa e contextualmente isolada.
- **Destino definido:** APIs separadas por aplicação, cada uma com repositório e ciclo de deploy independente.
- **Em aberto:** quais aplicações serão agrupadas ou permanecerão separadas — decisão de negócio ainda não tomada, sem impacto técnico imediato.

### Grupo C — Outros
- Aplicações sem ligação entre si e sem domínio compartilhado. O nome "Pessoal" foi revisado para "Outros" por refletir melhor a natureza heterogênea do grupo.
- Usuário único em todas — exclusivamente o próprio desenvolvedor.
- **Destino definido:** aplicações totalmente independentes entre si, sem integração de navegação, sem banco compartilhado.

---

## 2. Identidade e Autenticação

### Requisitos definidos
- SSO dentro de cada grupo.
- Login social via OAuth2 / Google.
- Controle de acesso por e-mail (apenas determinados endereços podem se registrar).
- Suporte a MFA e recuperação de senha.
- Suporte futuro a múltiplos usuários reais (hoje cada aplicação usa usuário fixo/configurado).
- Adoção de padrões abertos como JWT para facilitar interoperabilidade com frameworks, ferramentas de teste e agentes de IA.

### Preferências definidas
- Usar **solução pronta**, não construída do zero — sem reinventar roda.
- Evitar over engineering.
- Keycloak foi avaliado como pesado demais para o porte.

### Decisão
**Logto**, com **tenants isolados por grupo**.

Logto cobre todos os requisitos (OAuth2/Google, MFA, OIDC, JWT padrão, admin GUI, allowlist de e-mails), tem footprint significativamente menor que o Authentik (que consome ~375MB só no servidor + ~360MB no worker em idle), e foi desenhado para reduzir a complexidade de setups de porte pequeno a médio.

A instância do Logto é única e compartilhada como serviço de infraestrutura, mas cada grupo opera em seu próprio tenant isolado:

| Grupo | Tenant | Usuários |
|---|---|---|
| Família | `tenant-familia` | Membros da família |
| Trabalho | `tenant-trabalho` | Usuário único, porta aberta para um segundo |
| Outros | `tenant-outros` | Usuário único |

Essa separação por tenant é a **única** forma de compartilhamento entre os grupos. Dados, backends e bancos são completamente independentes entre si — não existe infraestrutura de dados cruzada entre grupos.

---

## 3. Arquitetura de Backend

### Situação atual
- Backends monolíticos por aplicação (frontend e backend no mesmo repositório e container Docker).
- Complexidade atual pequena — refatoração não é impeditivo técnico.

### Requisitos e intenções definidas
- Separar frontend e backend de cada aplicação.
- Backend deve ser projetado para sobreviver à unificação futura dos frontends — é o ativo de maior longevidade.
- APIs reutilizáveis entre aplicações do mesmo grupo são desejadas.
- Parte das funcionalidades deverá ser exposta para agentes de IA via MCP — o que pressiona por APIs bem definidas e separação clara entre interface e lógica de negócio.

### Decisão por grupo

**Grupo Família — backend monolítico único, Python + FastAPI.**

Um único repositório de backend com APIs organizadas internamente por domínio de negócio. A coesão do domínio familiar e o fato de as funcionalidades compartilharem dados justificam o monolito — não há nada a ganhar com separação aqui.

```
familia-backend/
├── app/
│   ├── main.py
│   ├── domains/
│   │   ├── orcamento/
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── services.py
│   │   │   └── routes.py
│   │   ├── lista_compras/
│   │   │   └── ...
│   │   └── compromissos/
│   │       └── ...
│   └── shared/
│       └── auth.py       # validação JWT + upsert do usuário local
├── migrations/           # Alembic, todas as tabelas do grupo
├── Dockerfile
└── docker-compose.yml
```

**Grupo Trabalho — APIs separadas por aplicação, Python + FastAPI.**

Cada aplicação tem seu próprio repositório, container Docker e ciclo de deploy independente. Nenhuma atualização em uma aplicação afeta ou exige intervenção nas demais.

```
trabalho-atividades/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── services.py
│   └── auth.py           # validação JWT + upsert do usuário local
├── migrations/
├── Dockerfile
└── docker-compose.yml
```

**Grupo Outros — APIs separadas por aplicação, Python + FastAPI.**

Mesma estrutura do Grupo Trabalho. Cada aplicação é completamente autônoma.

---

Em todos os grupos, FastAPI é o framework de backend pelas mesmas razões: gera OpenAPI spec automaticamente (facilitando a futura exposição via MCP sem retrabalho), é leve, e tem o melhor ecossistema Python de integração com LLMs do mercado.

A separação entre `services.py` e as rotas não é detalhe estético — é o que permitirá reutilizar a lógica tanto via API REST quanto via MCP no futuro, sem reescrita de código.

---

## 4. Arquitetura de Frontend

### Decisão por grupo

**Grupo Família:** React com Capacitor para empacotamento mobile. Um único repositório de frontend que agrega todas as funcionalidades do grupo, com novas funcionalidades sendo adicionadas gradualmente ao menu. Mobile-first desde o início.

**Grupo Trabalho:** cada aplicação mantém seu próprio frontend independente. O menu de chaveamento é implementado como **links simples com SSO** — um componente de navegação leve injetado no header de cada app, com ícones/atalhos para as demais. Como o SSO via Logto é transversal ao grupo, o usuário já estará autenticado ao navegar entre as aplicações, sem necessidade de micro-frontend ou arquitetura mais complexa.

**Grupo Outros:** sem integração de navegação. Cada aplicação é completamente autônoma.

---

## 5. Persistência e Banco de Dados

### Situação atual
- Persistência majoritariamente file-based por simplicidade.
- Já existe PostgreSQL rodando no servidor, atualmente utilizado apenas por aplicações de terceiros.

### Requisitos e intenções definidas
- Migração de file-based para banco relacional é necessária e inevitável.
- Preferência por migrar direto para o modelo final e definitivo, aproveitando a refatoração obrigatória para evitar retrabalho futuro.
- Cada aplicação deve poder evoluir e fazer deploy de forma independente, atualizando apenas suas próprias tabelas.
- Existe necessidade de espaço seguro para experimentação, separado do ambiente de produção.

### Decisão
**Um servidor PostgreSQL, dois databases por grupo (`prod` e `dev`), sem schemas explícitos, sem infraestrutura de dados compartilhada entre grupos.**

| Database | Propósito |
|---|---|
| `caramello` | Produção do Grupo Família |
| `caramello_dev` | Desenvolvimento e testes de integração (rollback por teste) |
| `trabalho_prod` | Produção do Grupo Trabalho |
| `trabalho_dev` | Desenvolvimento do Grupo Trabalho |
| `outros_prod` | Produção do Grupo Outros |
| `outros_dev` | Desenvolvimento do Grupo Outros |

Dentro de cada database, sem uso de schemas PostgreSQL — o isolamento é feito por convenção de nomenclatura das tabelas (prefixo por domínio, ex.: `orcamento_lancamentos`, `lista_itens`). Isso é suficiente dado que não há risco real de conflito entre domínios de negócio distintos dentro de um mesmo grupo.

Cada aplicação gerencia suas próprias migrations via **Alembic** e opera exclusivamente sobre suas tabelas — deploy completamente independente, sem risco de regressão entre aplicações.

---

## 6. Modelo de Usuários por Grupo — Decisão de Desacoplamento

Esta é uma das decisões arquiteturais mais relevantes do projeto, pois elimina o único ponto de acoplamento que existia entre grupos na versão anterior da arquitetura.

### O problema que foi descartado

Uma versão anterior desta arquitetura considerava uma tabela `users` compartilhada entre todas as aplicações, gerenciada por um repositório de infraestrutura dedicado chamado `plataforma-core`. Esse modelo foi descartado porque criava acoplamento entre grupos que têm perfis, usuários e domínios completamente distintos — uma complexidade sem benefício real para o contexto deste projeto.

### A decisão: cada grupo é uma ilha completa

Cada grupo possui seus próprios usuários, sua própria tabela `users`, e não conhece nem depende dos usuários de nenhum outro grupo. O Logto é o único elo entre os grupos — e apenas como serviço de infraestrutura de autenticação, não como dado compartilhado.

### Como funciona em cada grupo

**Grupo Família**

A tabela `users` vive no database `caramello`, gerenciada pelas migrations do backend monolítico do grupo. Ela registra os membros da família que se autenticaram pelo tenant `tenant-familia` do Logto.

```sql
CREATE TABLE users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idp_sub    TEXT NOT NULL UNIQUE,  -- "sub" do JWT emitido pelo Logto
    email      TEXT NOT NULL UNIQUE,
    name       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Todas as tabelas de domínio do grupo referenciam `users.id` com foreign key. O registro do usuário é criado automaticamente no primeiro acesso via **just-in-time provisioning** — sem fluxo de cadastro separado.

**Grupo Trabalho**

Cada aplicação do grupo possui sua própria tabela `users` no seu próprio database. Como o grupo tem predominantemente um único usuário, essa tabela terá na prática um único registro — mas a estrutura é idêntica à do Grupo Família, mantendo o padrão e deixando a porta aberta para um eventual segundo usuário sem nenhuma mudança arquitetural.

A independência aqui é total: não existe nenhuma tabela compartilhada entre as aplicações do grupo, nem entre o grupo e os demais. Cada aplicação gerencia seu próprio `users` via suas próprias migrations.

**Grupo Outros**

Mesma estrutura do Grupo Trabalho. Cada aplicação tem sua tabela `users` local com um único registro. O uso do Logto não é motivado por segurança robusta, mas por **interoperabilidade por convenção**: o JWT emitido pelo Logto é um padrão reconhecido por middlewares, frameworks, ferramentas de teste e agentes de IA — sem necessidade de explicar ou customizar o mecanismo de autenticação em cada aplicação.

### O que o `plataforma-core` seria e por que foi descartado

Na arquitetura anterior, o `plataforma-core` seria um repositório dedicado a gerenciar a migration da tabela `users` compartilhada, criando uma dependência de sequência de execução entre todos os grupos. Sua existência introduzia três problemas:

**Acoplamento implícito de deploy** — qualquer ambiente novo precisaria rodar o `plataforma-core` antes de qualquer outra aplicação, criando uma dependência operacional invisível para quem não conhece a arquitetura.

**Falsa economia** — a tabela `users` de cada grupo tem perfil de usuários, campos e semântica distintos. Forçar uma tabela única compartilhada significaria criar uma tabela genérica demais ou adicionar colunas que só fazem sentido para alguns grupos.

**Violação do princípio de ilha** — grupos com domínios completamente independentes não deveriam compartilhar dado algum. O único compartilhamento legítimo é o serviço de autenticação (Logto), não os dados de usuário em si.

A decisão de eliminar o `plataforma-core` simplifica o modelo operacional sem abrir mão de nenhum requisito real do projeto.

### Resumo do modelo de usuários

| Grupo | Tabela `users` | Dono das migrations | Usuários esperados |
|---|---|---|---|
| Família | `caramello.users` | Backend monolítico do grupo | Membros da família |
| Trabalho (por app) | `trabalho_prod.users` | Cada aplicação individualmente | 1, porta aberta para 2 |
| Outros (por app) | `outros_prod.users` | Cada aplicação individualmente | 1 (usuário único) |

---

## 7. Integração com IA e MCP

### Requisitos e intenções definidas
- Parte das funcionalidades deverá ser exposta para agentes de IA.
- Intenção de adicionar camada MCP sobre APIs existentes.
- Isso pressiona por: APIs bem definidas, separação clara entre interface e lógica de negócio, e backend com bom ecossistema de integração com LLMs.

### Posição arquitetural
A escolha de FastAPI resolve boa parte desse requisito de forma automática: a OpenAPI spec gerada pelo framework é o insumo direto para a construção de servidores MCP. A separação de lógica em `services.py` garante que os endpoints MCP futuros sejam wrappers finos sobre código já existente e testado — sem duplicação de lógica de negócio.

O JWT padrão emitido pelo Logto também contribui aqui: agentes de IA que conhecem o padrão OIDC/JWT conseguem autenticar e operar nas APIs sem configuração especial.

Não há nada a construir agora além de manter essa disciplina arquitetural desde o início.

---

## 8. Restrições e Premissas

- Uso pessoal e familiar.
- 1 a 5 usuários simultâneos — sem necessidade de escala.
- Microserviços por escala não fazem sentido para este contexto.
- Prioridades: simplicidade operacional, manutenibilidade, evolução gradual sem retrabalho, liberdade de experimentação, preparação para IA e MCP, evitar over engineering.

---

## 9. Quadro de Decisões

| Questão | Decisão |
|---|---|
| Provedor de identidade | **Logto** — leve, cobre OAuth2/Google + MFA + JWT padrão |
| Modelo de tenants | **Um tenant por grupo** — Família, Trabalho e Outros isolados |
| Linguagem do backend | **Python** |
| Framework de backend | **FastAPI** — OpenAPI automático, ecossistema IA/LLM, leve |
| Backend Grupo Família | **Monolítico único** — domínio coeso justifica o monolito |
| Backend Grupo Trabalho | **APIs separadas por aplicação** — deploy independente por design |
| Backend Grupo Outros | **APIs separadas por aplicação** — aplicações sem ligação entre si |
| Banco de dados | **Um servidor PostgreSQL, dois databases por grupo** (`prod` e `dev`) |
| Schemas PostgreSQL | **Não** — isolamento por nomenclatura de tabelas é suficiente |
| Migrations | **Alembic** por aplicação/monolito, operando apenas sobre suas próprias tabelas |
| Tabela `users` | **Local por aplicação/grupo** — sem compartilhamento entre grupos |
| `plataforma-core` | **Descartado** — acoplamento sem benefício real para este contexto |
| Menu de chaveamento Grupo Trabalho | **Links simples com SSO** via componente de navegação compartilhado |
| Autenticação Grupo Outros | **Logto** — por interoperabilidade JWT, não por necessidade de segurança robusta |

---

## 10. Questões Ainda em Aberto

1. **Grupo Trabalho:** quais aplicações serão agrupadas ou permanecerão separadas — decisão de negócio pendente, sem impacto técnico imediato.

---

## 11. Sequência de Implementação Sugerida

A fundação de infraestrutura vem primeiro, antes de qualquer aplicação:

1. Subir PostgreSQL com os databases de cada grupo (`caramello`, `caramello_dev`, `trabalho_prod`, `trabalho_dev`, `outros_prod`, `outros_dev`)
2. Instalar e configurar Logto com os três tenants (`tenant-familia`, `tenant-trabalho`, `tenant-outros`)
3. Configurar OAuth2/Google, MFA e allowlist de e-mails em cada tenant
4. Definir e documentar o template base de backend (FastAPI + Alembic + estrutura de pastas padrão)
5. Implementar o Grupo Família primeiro — o monolito é o caso mais representativo para validar toda a fundação na prática
6. A partir daí, cada nova aplicação dos demais grupos segue o template e integra o tenant correspondente do Logto desde o início

