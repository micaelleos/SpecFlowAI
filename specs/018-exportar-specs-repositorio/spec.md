# F18 — Exportar specs para o repositório (formato Spec Kit, por PR)

| Campo | Valor |
|---|---|
| **Status** | Em implementação |
| **Fase** | 4 — Evolução |
| **Responsável** | PO |
| **Dependências** | F06, F10, F17 |
| **ADRs relacionados** | ADR-003, ADR-007, ADR-010, ADR-011 |
| **Estimativa** | 4 dias |

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md) · [Doc 10 — Specs para agentes](../../docs/modernizacao/10-specs-para-agentes.md)

**Revisão 2026-11-27 (contra o código, antes da implementação; PO escolheu a F18):**
- **Credencial:** o mesmo token fine-grained da F17, com `Contents: Read and write` e `Pull requests: Read and write` (escolha do PO; ADR-011).
- **Ponto de partida:**
  - no chat, o agente propõe a exportação ("exporte o épico ABC-10 para o repositório");
  - em Created issues, cada épico tem "Export to repository", que abre o chat com o pedido.
- **Conteúdo:** sai do histórico da F10, ou seja, das specs que o SpecFlow criou, sem o LLM reescrever nada.

---

## Parte A — Especificação (Gate 0)

### 1. Contexto e objetivo
- **Problema:** parte dos times prefere specs versionadas junto do código (Spec Kit, Kiro), onde o agente de código as encontra sem passar pelo Jira.
- **Objetivo:** o PO exporta um épico e as histórias dele para o repositório vinculado ao projeto, como arquivos Markdown no formato Spec Kit, num PR que o time revisa.
- **Indicador:** PRs de spec abertos por mês.

### 2. Escopo
- **Dentro:**
  - `specs/<nnn>-<slug>/spec.md` e `tasks.md` gerados a partir dos `AgentReadySpec` do épico e das histórias;
  - branch `specflow/<chave>` e PR para a branch padrão;
  - link do épico no Jira para o PR;
  - confirmação humana antes de qualquer escrita (Art. IV).
- **Fora:**
  - sincronização Jira ↔ repositório;
  - outros formatos além de Spec Kit;
  - atualizar um PR já aberto;
  - histórias que o SpecFlow não criou.

### 3. Requisitos funcionais
| ID | Requisito | Prioridade |
|---|---|---|
| F18-RF-01 | O PO pede para exportar um épico criado pelo SpecFlow e vê, no cartão, o repositório, a branch, os arquivos (com o conteúdo) e o título do PR | Must |
| F18-RF-02 | Ao confirmar, o SpecFlow cria a branch, grava os arquivos e abre o PR com os links para as issues do Jira; o cartão mostra o link do PR | Must |
| F18-RF-03 | `spec.md` traz o épico e cada história com as seções fixas do contrato (doc 10 §4.2) e os IDs `CA-nn`; `tasks.md` traz uma tarefa por história com a chave do Jira; a pasta usa o próximo número livre em `specs/` | Must |
| F18-RF-04 | O épico no Jira recebe um link para o PR | Should |
| F18-RF-05 | Sem repositório vinculado, sem épico do SpecFlow ou sem permissão de escrita no token, não há escrita e a mensagem diz o que falta | Must |

### 4. Requisitos técnicos / não funcionais
| ID | Requisito | Verificação |
|---|---|---|
| F18-RT-01 | Abrir o PR é uma ação proposta (ADR-003): os arquivos estão no payload e o hash é conferido na execução | unit |
| F18-RT-02 | Nunca escreve na branch padrão: só cria `specflow/<chave>` (com sufixo se existir), grava nela e abre o PR; escrita não é repetida | unit |
| F18-RT-03 | O conteúdo dos arquivos sai das specs guardadas (sem LLM), com caminhos validados e tamanho limitado (≤ 200 KB no total) | unit |
| F18-RT-04 | Auditoria `github_write` (ação, repositório, número do PR, resultado), sem conteúdo | unit |

### 5. Teste final de aceitação
```gherkin
Funcionalidade: Exportar specs para o repositório

  Cenário: AT-F18-01 Exportar épico como PR                        # F18-RF-01..04
    Dado um épico com 2 histórias criadas pelo SpecFlow num projeto com repositório vinculado
    Quando peço para exportar o épico e confirmo o cartão
    Então existe um PR com "specs/<nnn>-<slug>/spec.md" e "tasks.md" na branch "specflow/<chave>"
    E o spec.md tem "Objetivo", "Critérios de aceite" e "Fora de escopo" de cada história
    E o épico no Jira tem um link para o PR

  Cenário: AT-F18-02 Recusar não escreve                           # F18-RF-01, F18-RT-01
    Dado o cartão de exportação
    Quando recuso
    Então nenhuma branch nem PR é criado

  Cenário: AT-F18-03 Sem repositório                               # F18-RF-05
    Dado um projeto sem repositório vinculado
    Quando peço para exportar um épico
    Então o agente diz para vincular um repositório em Projects e não há cartão
```

### 6. Conformidade com a Constituição
| Artigo | Cumprimento | Exceção? |
|---|---|---|
| II Privacidade | Ação sob `users/{uid}`; o conteúdo vai ao repositório só depois do Confirm | Não |
| III Segredos | O mesmo token cifrado da F17 | Não |
| IV Confirmação | Ação proposta e Confirm, com o mesmo hash; só branch própria | Não |
| V Contrato | `create_pull_request` no OpenAPI e no esquema SSE | Não |
| VI Testes | unit, Vitest, evals, AT-F18-01..03 | Não |
| IX Observabilidade | `github_write` | Não |
| XI Evals | `f18_v1`: exporta quando pedido, não exporta sem pedido nem sem repositório | Não |
| XII Contrato da spec | Os arquivos usam o mesmo `AgentReadySpec` e a mesma renderização do Jira | Não |

---

## Parte C — Validação (Gates 3 e 4)

### 10. Rastreabilidade
| Requisito | Teste(s) | Status |
|---|---|---|
| F18-RF-01 | — | ⏳ |
| F18-RF-02 | — | ⏳ |
| F18-RF-03 | — | ⏳ |
| F18-RF-04 | — | ⏳ |
| F18-RF-05 | — | ⏳ |

### 11. Evidências
| Data | Versão/commit | Ambiente | Execução (link CI) | Resultado | Aceito por |
|---|---|---|---|---|---|
