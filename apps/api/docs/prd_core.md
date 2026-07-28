# PRD Core – Autenticação, Usuários e Famílias

## 1. Objetivo do Documento

Este documento descreve os requisitos funcionais centrais do Caramello relacionados à autenticação de usuários, gestão de famílias, papéis, permissões e integrações básicas. Ele serve como referência funcional para implementação, testes e evolução do produto, complementando a Visão do Projeto.

Este PRD não aborda decisões técnicas, arquitetura, modelagem de dados ou escolhas de frameworks.

---

## 2. Escopo do PRD Core (MVP)

### 2.1 Funcionalidades Incluídas

* Autenticação de usuários
* Criação e gestão de famílias
* Papéis de owner e membro
* Convites para entrada em famílias
* Aprovação de solicitações
* Seleção e troca de família ativa
* Vinculação conceitual de integrações por usuário

### 2.2 Fora de Escopo

* Funcionalidades de agenda
* Listas, saúde, entretenimento
* Integrações específicas com serviços externos
* Configurações avançadas de permissões

---

## 3. Conceitos Fundamentais

### Usuário

Pessoa autenticada no sistema, identificada de forma única e persistente.

### Família

Unidade central de organização do Caramello, onde dados compartilhados são agrupados.

### Owner da Família

Usuário responsável pela criação da família, com poderes administrativos exclusivos.

### Membro da Família

Usuário participante da família, com acesso às funcionalidades conforme regras do produto.

### Família Ativa

Família atualmente selecionada pelo usuário para interação no sistema.

### Convite

Código ou link gerado pelo owner para permitir que outros usuários solicitem entrada na família.

### Solicitação de Entrada

Pedido gerado quando um usuário utiliza um convite para ingressar em uma família, sujeito à aprovação.

### Integração de Serviço

Vinculação entre um usuário e um serviço externo, permitindo acesso a funcionalidades específicas.

---

## 4. Papéis, Permissões e Responsabilidades

### Owner

* Criar a família
* Gerar e revogar convites
* Aprovar ou rejeitar solicitações de entrada
* Visualizar e remover membros

### Membro

* Acessar funcionalidades da família
* Visualizar outros membros
* Solicitar saída da família

### Restrições

* Existe apenas um owner por família
* O owner não pode remover a si mesmo

---

## 5. Fluxo de Autenticação

### 5.1 Login Inicial

* Usuário realiza login por meio de provedor de identidade
* Caso seja o primeiro acesso, um novo usuário é criado

### 5.2 Sessão Ativa

* Usuário autenticado pode acessar funcionalidades conforme permissões

### 5.3 Logout

* Usuário pode encerrar sua sessão a qualquer momento

### 5.4 Reautenticação

* Sessões expiradas exigem novo login

---

## 6. Gestão de Famílias

### 6.1 Criação de Família

* Usuário autenticado pode criar uma nova família
* Ao criar, torna-se automaticamente o owner

### 6.2 Seleção de Família Ativa

* Usuários com apenas uma família têm seleção automática
* Usuários com múltiplas famílias devem escolher uma família ativa

### 6.3 Troca de Família Ativa

* Usuário pode alternar a família ativa a qualquer momento

---

## 7. Convites e Entrada em Famílias

### 7.1 Geração de Convite

* Apenas o owner pode gerar convites
* Convites são reutilizáveis
* Convites podem ser revogados

### 7.2 Solicitação de Entrada

* Usuário autenticado utiliza convite para solicitar entrada
* Solicitação fica em estado pendente

### 7.3 Aprovação ou Rejeição

* Owner aprova ou rejeita solicitações
* Aprovação concede acesso imediato
* Rejeição encerra a solicitação

---

## 8. Gestão de Membros da Família

* Owner pode visualizar todos os membros
* Owner pode remover membros
* Membro pode solicitar saída voluntária

---

## 9. Integrações de Serviços (Visão Geral)

* Integrações são vinculadas a usuários
* Cada integração possui estado próprio (ativa, revogada, erro)
* Funcionalidades dependem da integração ativa

---

## 10. Regras Gerais de Privacidade e Acesso

* Dados são sempre isolados por família
* Dados individuais não são automaticamente compartilhados
* Acesso a dados sensíveis deve ser explícito

---

## 11. Estados, Erros e Situações Excepcionais

* Acesso sem família ativa não é permitido
* Convite inválido gera erro informativo
* Solicitações duplicadas não são permitidas
* Falhas de integração devem ser comunicadas

---

## 12. Experiência do Usuário (Visão Funcional)

### Onboarding

* Login
* Criação ou entrada em família

### Usuário sem Família

* Pode criar família ou inserir convite

### Usuário com Solicitação Pendente

* Acesso bloqueado até decisão do owner

### Usuário com Múltiplas Famílias

* Deve escolher família ativa

---

## 13. Fora de Escopo e Decisões Postergadas

* Papéis adicionais
* Delegação de permissões
* Automatizações

---

## 14. Critérios Gerais de Aceite (Core)

* Identidade do usuário consistente
* Isolamento total entre famílias
* Clareza nos estados de acesso
* Comportamento previsível e seguro

---

## 15. Considerações Finais

Este PRD Core estabelece a base funcional do Caramello. Funcionalidades adicionais devem ser descritas em PRDs específicos, mantendo este documento estável e focado no núcleo do sistema.
