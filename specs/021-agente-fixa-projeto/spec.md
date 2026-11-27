# F21 — O agente fixa o projeto da conversa

| Campo | Valor |
|---|---|
| **Status** | Em implementação |
| **Fase** | 4 — Evolução |
| **Responsável** | PO |
| **Dependências** | F07, F19, F20 |
| **ADRs relacionados** | ADR-003, ADR-009 |
| **Estimativa** | 2,5 dias |

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

**Decisões do PO (2026-11-27):**
- O agente pode fixar o projeto numa conversa que ainda não tem projeto.
- O agente **não** troca nem solta o projeto. O usuário continua podendo soltar pelo × da tela (F07).
- Depois de fixar, a **mesma resposta** continua com a documentação do projeto: o agente lê o espaço vinculado e pode propor a alteração pedida.
- O usuário também fixa o projeto à mão numa conversa sem projeto, por um seletor no topo do chat.

---

## Parte A — Especificação (Gate 0)

### 1. Contexto e objetivo
- **Problema:** em teste do PO em prd (2026-11-27), numa conversa aberta sem projeto, o agente não tinha as ferramentas do Confluence. O usuário precisava sair do chat e abrir *Chat about this project* em Projects para o agente alterar páginas.
- **Objetivo:** quando o usuário diz de qual projeto está falando, o agente fixa a conversa nesse projeto e segue na mesma resposta com o contexto dele: índice do espaço, leitura e escrita por ação proposta (F19/F20).
- **Indicador de sucesso:** um pedido de documentação feito numa conversa nova, sem projeto, termina com a proposta da página no mesmo turno em que o usuário nomeia o projeto.

### 2. Escopo
- **Dentro:**
  - ferramenta `fixar_projeto_da_conversa`, oferecida só em conversa sem projeto e com Jira conectado;
  - continuação do turno com o contexto do projeto;
  - o projeto fixado aparece no topo do chat ao fim da resposta;
  - seletor "Pin a project" no topo do chat de uma conversa sem projeto.
- **Fora:**
  - trocar ou soltar o projeto pelo agente;
  - vincular projeto ↔ espaço do Confluence pelo agente (continua em Projects, F19);
  - fixar mais de um projeto.

### 3. Requisitos funcionais
| ID | Requisito | Prioridade |
|---|---|---|
| F21-RF-01 | Numa conversa sem projeto, com Jira conectado, o agente fixa a conversa num projeto quando o usuário nomeia o projeto ou confirma a sugestão do agente. A chave precisa estar entre os projetos que a conta vê; se não estiver, o agente diz isso e pergunta | Must |
| F21-RF-02 | Depois de fixar, a mesma resposta continua com o contexto do projeto: instrução do projeto, índice do espaço vinculado e ferramentas do Confluence conforme as flags (F19/F20). Sem espaço vinculado, segue como numa conversa fixada sem vínculo | Must |
| F21-RF-03 | O agente não troca nem solta o projeto: a ferramenta não existe numa conversa com projeto e recusa se a conversa já tiver projeto. O × da tela continua soltando (F07) | Must |
| F21-RF-04 | Ao fim da resposta, o chip "Pinned project" mostra o projeto fixado, sem recarregar a página | Must |
| F21-RF-05 | Numa conversa sem projeto, o topo do chat mostra o seletor "Pin a project" com os projetos do Jira da conta; escolher um fixa a conversa (o mesmo `PATCH` da F07), e a próxima mensagem já usa o contexto do projeto | Must |

### 4. Requisitos técnicos / não funcionais
| ID | Requisito | Verificação |
|---|---|---|
| F21-RT-01 | A gravação só acontece se `projectKey` ainda estiver vazio (transação no Firestore); nunca sobrescreve um projeto já fixado | integração |
| F21-RT-02 | `agent` não importa `repositories`: recebe a interface `ConversationPinner` no `ToolContext` | import-linter |
| F21-RT-03 | Uma fixação por turno; a continuação reaproveita as mensagens do turno (chamada e resposta da ferramenta) e o limite de iterações do turno | unit |
| F21-RT-04 | Log `conversation_pinned` com `uid_hash` e a chave do projeto, sem conteúdo | unit |
| F21-RT-05 | Evals com casos de fixação (pede doc sem projeto; projeto inexistente; não troca projeto) | evals |

### 5. Teste final de aceitação
```gherkin
Funcionalidade: O agente fixa o projeto da conversa

  Cenário: AT-F21-01 Pedido de documentação numa conversa nova       # F21-RF-01, F21-RF-02, F21-RF-04
    Dado o projeto SCRUM vinculado a um espaço do Confluence
    E uma conversa nova, sem projeto
    Quando peço "No projeto SCRUM, adicione ao glossário o termo Cupom"
    Então o agente fixa a conversa no SCRUM
    E na mesma resposta propõe a atualização do Glossário
    E o topo do chat mostra "Pinned project: SCRUM"

  Cenário: AT-F21-02 O agente não troca o projeto                   # F21-RF-03
    Dado uma conversa fixada no SCRUM
    Quando peço "agora fixe esta conversa no projeto VEND"
    Então o projeto continua SCRUM
    E o agente explica que a troca é pelo × no topo do chat ou numa conversa nova

  Cenário: AT-F21-04 Pin manual                                     # F21-RF-05
    Dado uma conversa sem projeto
    Quando escolho SCRUM em "Pin a project"
    Então o topo do chat mostra "Pinned project: SCRUM"
    E a próxima resposta usa a documentação do SCRUM

  Cenário: AT-F21-03 Projeto que a conta não vê                     # F21-RF-01
    Dado uma conversa nova, sem projeto
    Quando peço para fixar o projeto XYZ, que não existe na minha conta
    Então nada é fixado e o agente mostra os projetos disponíveis
```

### 6. Conformidade com a Constituição
| Artigo | Cumprimento | Exceção? |
|---|---|---|
| II Privacidade | Gravação em `users/{uid}/conversations/{id}`; `uid` do token | Não |
| IV Confirmação | Fixar o projeto é estado interno da conversa, não escrita externa; as escritas no Confluence/Jira continuam por ação proposta | Não |
| VI Testes | unit, integração, Vitest, evals e AT-F21-01..04 | Não |
| X Acessibilidade | Seletor com rótulo, operável por teclado | Não |
| IX Observabilidade | `conversation_pinned` | Não |
| XI Evals | casos novos no conjunto da F05 | Não |

---

## Parte C — Validação (Gates 3 e 4)

### 10. Rastreabilidade
| Requisito | Teste(s) | Status |
|---|---|---|
| F21-RF-01 | — | ⏳ |
| F21-RF-02 | — | ⏳ |
| F21-RF-03 | — | ⏳ |
| F21-RF-04 | — | ⏳ |
| F21-RF-05 | — | ⏳ |

### 11. Evidências
| Data | Versão/commit | Ambiente | Execução (link CI) | Resultado | Aceito por |
|---|---|---|---|---|---|
