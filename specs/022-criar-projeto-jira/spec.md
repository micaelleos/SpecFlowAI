# F22 — O agente cria projetos no Jira (ação proposta)

| Campo | Valor |
|---|---|
| **Status** | Em implementação |
| **Fase** | 4 — Evolução |
| **Responsável** | PO |
| **Dependências** | F06, F09, F21 |
| **ADRs relacionados** | ADR-003, ADR-004 |
| **Estimativa** | 3 dias |

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

**Pedido do PO (2026-11-27):** o agente pode criar projetos no Jira.

**Decisões padrão:** sem nova pergunta ao PO; dá para mudar na revisão do PR.
- **Confirmação:** criar projeto é escrita no Jira, então segue a ação proposta da F06. O cartão mostra nome, chave, modelo e responsável, e nada é criado antes do Confirm.
- **Responsável (lead):** a própria conta Atlassian conectada.
- **Modelos:** três modelos *company-managed*. Os *team-managed* não entram, porque a API da Atlassian não os cria de forma confiável.
- **Fixar o projeto:** numa conversa sem projeto, o projeto criado passa a ser o da conversa, com a mesma regra da F21 (só se estiver vazio).

---

## Parte A — Especificação (Gate 0)

### 1. Contexto e objetivo
- **Problema:** para começar um produto novo, o PO precisa sair do SpecFlow, criar o projeto no Jira e voltar para conectar tudo.
- **Objetivo:** o PO pede no chat ("crie um projeto Loja Online, scrum"). O agente propõe o projeto com chave validada, o PO confirma e a conversa já segue com o projeto criado.
- **Indicador de sucesso:** projetos criados pelo SpecFlow sem falha de chave ou de modelo; nenhuma criação sem Confirm.

### 2. Escopo
- **Dentro:**
  - proposta de criação de projeto pelo agente (nome, chave, modelo, descrição);
  - chave validada no Jira antes de propor, com sugestão quando está em uso;
  - execução depois do Confirm, com o mesmo hash da F06;
  - fixar o projeto na conversa sem projeto;
  - atualizar a lista de Projects.
- **Fora:**
  - apagar, arquivar ou renomear projetos;
  - esquemas personalizados (workflow, permissões, telas);
  - projetos *team-managed*, de *service desk* ou de *customer service*;
  - escolher outro responsável que não a conta conectada.

### 3. Requisitos funcionais
| ID | Requisito | Prioridade |
|---|---|---|
| F22-RF-01 | Quando o usuário pede, o agente propõe criar um projeto com nome, chave, modelo (Scrum, Kanban ou tarefas de negócio) e descrição. O cartão mostra tudo, inclusive o responsável, e o projeto só é criado depois do Confirm | Must |
| F22-RF-02 | A chave é validada no Jira antes da proposta: formato e disponibilidade. Chave em uso ou inválida não vira cartão, e o agente recebe uma sugestão de chave livre | Must |
| F22-RF-03 | Depois de criar, a conversa sem projeto passa a ter o projeto criado e a resposta traz o link. A lista de Projects mostra o projeto novo | Must |
| F22-RF-04 | Sem permissão para criar projetos (403), o cartão diz que é preciso ser administrador do Jira e nada é criado | Must |
| F22-RF-05 | O agente só propõe criar projeto quando o usuário pede; não cria projeto para contornar a falta de um | Must |

### 4. Requisitos técnicos / não funcionais
| ID | Requisito | Verificação |
|---|---|---|
| F22-RT-01 | Mesma confirmação da F06: o hash do payload exibido é conferido na execução e a conexão tem de ser a mesma da proposta | unit |
| F22-RT-02 | Modelos numa lista fechada (`scrum` → `gh-simplified-scrum-classic`, `kanban` → `gh-simplified-kanban-classic`, `negocio` → `jira-core-simplified-task-tracking`); chave `^[A-Z][A-Z0-9]{1,9}$` e nome de 2 a 80 caracteres | unit |
| F22-RT-03 | `POST /rest/api/3/project` nunca é repetido depois de enviado; resposta incerta vira falha não repetível que pede para conferir no Jira | unit |
| F22-RT-04 | Auditoria `jira_write` com `kind=create_project` e a chave; o cache de projetos (F09) é descartado depois da criação | unit |

### 5. Teste final de aceitação
```gherkin
Funcionalidade: Criar projeto no Jira pelo agente

  Cenário: AT-F22-01 Criar e seguir com o projeto                 # F22-RF-01, F22-RF-03
    Dado o Jira sandbox conectado com uma conta administradora
    E uma conversa sem projeto
    Quando peço "crie um projeto Scrum chamado Teste SpecFlow <data>"
    Então vejo o cartão com nome, chave, modelo Scrum e o responsável
    Quando confirmo
    Então o projeto existe no Jira e a conversa passa a ter esse projeto

  Cenário: AT-F22-02 Chave em uso                                  # F22-RF-02
    Quando peço um projeto com a chave de um projeto que já existe
    Então não há cartão com essa chave e o agente sugere outra chave

  Cenário: AT-F22-03 Recusar                                       # F22-RF-01, F22-RF-05
    Dado o cartão de criação de projeto
    Quando recuso
    Então nenhum projeto é criado
```

### 6. Conformidade com a Constituição
| Artigo | Cumprimento | Exceção? |
|---|---|---|
| II Privacidade | Ação e vínculos sob `users/{uid}` | Não |
| III Segredos | A mesma credencial da F04; nada novo guardado | Não |
| IV Confirmação | Ação proposta e Confirm, com o mesmo hash (ADR-003) | Não |
| V Contrato | `ActionOut.kind` ganha `create_project`; OpenAPI e cliente TS regenerados | Não |
| VI Testes | unit, Vitest, evals, AT-F22-01..03 | Não |
| IX Observabilidade | `jira_write` com `kind=create_project` | Não |
| XI Evals | `f22_v1`: propõe quando pedido, não propõe sem pedido, chave em uso | Não |

---

## Parte C — Validação (Gates 3 e 4)

### 10. Rastreabilidade
| Requisito | Teste(s) | Status |
|---|---|---|
| F22-RF-01 | `test_project_tools.py`, `test_project_actions.py`, `ActionCard.test.tsx`, evals `f22_v1`, AT-F22-01/03 | ✅ (AT-F22-01 aguarda autorização de escrita) |
| F22-RF-02 | `test_jira_project_create.py`, `test_project_tools.py`, evals `f22_v1`, AT-F22-02 | ✅ |
| F22-RF-03 | `test_project_actions.py`, `ActionCard.test.tsx`, AT-F22-01 | ✅ (AT-F22-01 aguarda autorização de escrita) |
| F22-RF-04 | `test_project_actions.py` | ✅ |
| F22-RF-05 | `test_project_tools.py`, evals `f22_v1`, AT-F22-03 | ✅ |

### 11. Evidências
| Data | Versão/commit | Ambiente | Execução (link CI) | Resultado | Aceito por |
|---|---|---|---|---|---|
| 2026-11-27 | branch `feat/F22-criar-projeto-jira` | local (Vertex AI, `gemini-3.5-flash-lite`) | `evals/run.py --dataset f22_v1.jsonl` (`results/2026-11-27-…-f22.json`, `…-f22-run2.json`) | 1ª execução 5/6: o agente escolheu uma chave em uso e perguntou em vez de usar a sugerida. Ajustada a instrução (chave escolhida pelo agente → usa a sugerida). 2ª execução 6/6 | — |
| 2026-11-27 | branch `feat/F22-criar-projeto-jira` | local (emuladores + Jira sandbox + Vertex AI) | `E2E_EMULATORS=1 E2E_REAL_LLM=1 playwright test e2e/f22-criar-projeto.spec.ts` | AT-F22-02 ✅ e AT-F22-03 ✅, sem escrita no Jira (log: só a auditoria `rejected`); AT-F22-01 pulado: cria um projeto e precisa de `E2E_JIRA_WRITE=1` autorizado pelo PO | — |
