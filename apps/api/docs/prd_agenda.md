# PRD – Agenda Familiar

## 1. Objetivo do Documento

Este documento descreve os requisitos funcionais da **Agenda Familiar do Caramello**, definindo comportamentos, fluxos, regras e responsabilidades relacionadas ao uso de compromissos e eventos familiares. Ele complementa a Visão do Projeto e o PRD Core.

Este PRD não aborda decisões técnicas, modelagem de dados ou detalhes de integração em nível de API.

---

## 2. Escopo do PRD (MVP)

### 2.1 Funcionalidades Incluídas

* Agenda familiar compartilhada
* Criação, edição e remoção de compromissos
* Visualização por família e por membro
* Integração conceitual com agenda externa
* Sincronização básica de eventos

### 2.2 Fora de Escopo

* Agendas pessoais independentes da família
* Agendas profissionais
* Regras avançadas de recorrência
* Compartilhamento externo fora da família

---

## 3. Conceitos Fundamentais

### Agenda Familiar

Agenda compartilhada entre todos os membros da família, utilizada como referência central de compromissos coletivos.

### Compromisso

Evento com data e hora definidos, podendo representar compromissos familiares ou individuais visíveis no contexto da família.

### Membro Responsável

Membro da família associado a um compromisso, indicando quem está diretamente envolvido.

### Fonte de Verdade

A agenda externa vinculada pelo owner da família é considerada a fonte primária dos dados de compromissos.

---

## 4. Princípios da Agenda Familiar

* Existe **uma única agenda por família**
* A agenda pertence conceitualmente à família, não a um indivíduo
* Todos os membros visualizam os compromissos da agenda
* Compromissos podem estar associados a um ou mais membros
* O Caramello atua como interface de criação, visualização e organização

---

## 5. Papéis e Permissões

### Owner

* Vincular a agenda externa da família
* Criar, editar e remover compromissos
* Visualizar todos os compromissos

### Membro

* Criar compromissos
* Editar ou remover compromissos criados por si
* Visualizar todos os compromissos

---

## 6. Criação de Compromissos

### 6.1 Dados Funcionais do Compromisso

* Título
* Data e horário
* Local (opcional)
* Descrição (opcional)
* Membros envolvidos

### 6.2 Comportamento

* Qualquer membro pode criar um compromisso
* Compromissos criados passam a integrar a agenda familiar
* Compromissos podem envolver toda a família ou membros específicos

---

## 7. Edição e Remoção de Compromissos

### 7.1 Edição

* O criador do compromisso pode editá-lo
* O owner pode editar qualquer compromisso

### 7.2 Remoção

* O criador pode remover o compromisso
* O owner pode remover qualquer compromisso

---

## 8. Visualização da Agenda

### 8.1 Modos de Visualização

* Visão geral da família
* Visão filtrada por membro

### 8.2 Representação

* Compromissos são apresentados de forma cronológica
* Eventos passados permanecem acessíveis para consulta

---

## 9. Integração com Agenda Externa (Visão Funcional)

* A agenda externa é vinculada pelo owner da família
* O Caramello reflete os eventos da agenda externa
* Compromissos criados no Caramello devem aparecer na agenda externa

---

## 10. Sincronização e Consistência

* Alterações realizadas no Caramello devem refletir na agenda externa
* Alterações realizadas diretamente na agenda externa devem ser refletidas no Caramello
* Em caso de conflito, prevalece a última alteração conhecida

---

## 11. Estados e Situações Excepcionais

* Agenda não vinculada: funcionalidade indisponível
* Falha de sincronização: usuário informado
* Remoção da integração externa: agenda fica inacessível

---

## 12. Experiência do Usuário (Visão Funcional)

### Onboarding da Agenda

* Owner vincula agenda da família

### Uso Diário

* Visualização rápida dos próximos compromissos
* Criação simplificada de eventos

---

## 13. Fora de Escopo e Evoluções Futuras

* Regras avançadas de recorrência
* Notificações inteligentes
* Integração com múltiplas agendas externas
* Automação de compromissos por assistente virtual

---

## 14. Critérios de Aceite

* Todos os membros veem a mesma agenda
* Compromissos criados são sincronizados
* Permissões são respeitadas
* Falhas são comunicadas claramente

---

## 15. Considerações Finais

Este PRD define o comportamento funcional da Agenda Familiar do Caramello. Detalhes técnicos e de integração serão descritos em documentos específicos.
