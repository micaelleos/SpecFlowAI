# F14 — Editor de artefatos antes da exportação

| Campo | Valor |
|---|---|
| **Status** | Em validação |
| **Fase** | 4 — Evolução |
| **Responsável** | PO |
| **Dependências** | F06, F08 |
| **ADRs relacionados** | ADR-003, ADR-007 |
| **Estimativa** | 6 dias |

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

**Revisão 2026-11-27 (contra o código, antes da implementação; PO escolheu a F14):**
- **O que se edita:** propostas pendentes de `create_issue` e de `update_issue` que trazem a spec (história, tarefa ou épico). Ficam de fora as ações do Confluence (F20), que têm diff próprio, e a atualização só de título, prioridade ou labels.
- **Campos:** as seções do `AgentReadySpec` e a prioridade da criação. Tipo e pai **não** são editáveis, porque o tipo muda o esquema; para isso o usuário pede ao agente.
- **Prévia e prontidão ao vivo:** a API recalcula a prévia sem gravar (`POST …/preview`), e a tela consulta enquanto o usuário digita. Isso substitui o autosave de rascunho a cada 2 s e a coleção `users/{uid}/artifacts`: a edição só vale depois de "Save", e um rascunho não confirmado não vira dado.
- **Versões:** cada "Save" grava a nova versão na própria ação (payload, hash, prévia, prontidão, labels e `version`). Na primeira edição a versão do agente fica guardada, e "Restore agent version" volta a ela.
- **Confirmação:** o cartão manda o hash do que está na tela; se a ação mudou nesse meio-tempo, a API recusa com 409 `action-changed` (Art. IV).
- **"Refine with AI":** o botão de uma seção manda uma mensagem no chat. O agente lê a proposta (`ler_proposta`) e regrava a seção na **mesma** ação (`revisar_proposta`), sem criar cartão novo.

---

## Parte A — Especificação (Gate 0)

### 1. Contexto e objetivo
- **Problema:** para mudar uma vírgula numa story proposta, o usuário precisa pedir ao agente e esperar uma nova proposta, que vira um segundo cartão.
- **Objetivo:**
  - editar no próprio cartão, antes de confirmar, as seções da spec e a prioridade;
  - ver a prévia e a prontidão atualizadas enquanto edita;
  - pedir ao agente o refinamento de uma seção específica, na mesma proposta.
- **Indicador de sucesso:** % de propostas editadas antes de confirmar; queda no número de turnos por issue criada.

### 2. Escopo
- **Dentro:**
  - modo de edição do `ActionCard` (criação e atualização com spec);
  - versão nova a cada "Save", com hash novo;
  - "Restore agent version";
  - "Refine with AI" por seção;
  - o agente vê e respeita a versão editada.
- **Fora:**
  - edição colaborativa em tempo real;
  - editar tipo, pai, projeto ou labels;
  - editar propostas do Confluence;
  - rascunho salvo sem "Save".

### 3. Requisitos funcionais
| ID | Requisito | Prioridade |
|---|---|---|
| F14-RF-01 | Numa proposta pendente com spec, "Edit" abre o editor por seção, com prévia e prontidão recalculadas enquanto o usuário edita | Must |
| F14-RF-02 | Ao confirmar, é criado ou atualizado no Jira exatamente o conteúdo salvo que está na tela | Must |
| F14-RF-03 | "Restore agent version" volta a proposta à última versão do agente; "Cancel" descarta o que não foi salvo | Should |
| F14-RF-04 | "Refine with AI" numa seção manda ao agente uma instrução, e ele regrava essa seção na mesma proposta | Should |
| F14-RF-05 | O agente considera a versão editada nos turnos seguintes (título e estado "editada pelo usuário" no estado das ações; conteúdo por `ler_proposta`) | Must |
| F14-RF-06 | O editor segue as seções do `AgentReadySpec`: objetivo, contexto, cada critério de aceite (título, tipo, Dado, Quando, Então), fora de escopo, restrições, onde mexer, como verificar, dúvidas em aberto e, no épico, problema, benefícios, escopo, critérios, decomposição e riscos. A prontidão é reavaliada a cada mudança | Must |

### 4. Requisitos técnicos / não funcionais
| ID | Requisito | Verificação |
|---|---|---|
| F14-RT-01 | "Save" grava a versão nova na ação (`payload`, `payloadHash`, prévia, prontidão, labels, `version`, `editedBy`), só se o `base_hash` enviado for o hash atual; senão, 409 `action-changed`. A confirmação com `payload_hash` diferente do atual também é recusada com 409 | unit + integração |
| F14-RT-02 | A validação da edição usa o mesmo esquema Pydantic da ferramenta do agente (`AgentReadySpec`), e o payload sai das mesmas funções (`create_payload`/`update_payload`) | contrato |
| F14-RT-03 | Prévia sem gravar (`POST /api/v1/actions/{id}/preview`), consultada com debounce na tela | unit + Vitest |
| F14-RT-04 | Seções obrigatórias não somem: o editor mostra todas e permite esvaziar (o que derruba a prontidão); a spec salva sempre valida no esquema (IDs `CA-nn` renumerados, limites de tamanho) | unit + Vitest |
| F14-RT-05 | Só a dona da ação edita (`users/{uid}`), só com status `pending` e não expirada; auditoria `action_edited` (`uid_hash`, `action_id`, `version`, `by`) | unit + integração |

### 5. Teste final de aceitação
```gherkin
Funcionalidade: Editar a proposta antes de confirmar

  Cenário: AT-F14-01 Editar e confirmar                         # F14-RF-01, F14-RF-02, F14-RF-06
    Dado uma proposta de story pendente
    Quando abro "Edit", mudo o título para "Login com SSO" e acrescento um critério de aceite
    Então a prévia e a prontidão mudam antes de salvar
    Quando salvo e confirmo
    Então a issue no Jira tem o título "Login com SSO" e o critério novo

  Cenário: AT-F14-02 Restaurar a versão do agente                # F14-RF-03
    Dado uma proposta que editei e salvei
    Quando clico em "Restore agent version"
    Então o cartão volta ao título que o agente propôs

  Cenário: AT-F14-03 Refinar uma seção com IA                    # F14-RF-04, F14-RF-05
    Dado uma proposta que editei, com o título "Login com SSO"
    Quando peço em "Refine with AI" nos critérios: "adicione o cenário de senha expirada"
    Então a mesma proposta passa a ter um critério sobre senha expirada
    E o título continua "Login com SSO"

  Cenário: AT-F14-04 Confirmação de versão desatualizada         # F14-RT-01
    Dado o cartão aberto em duas abas
    Quando salvo uma edição numa aba e confirmo na outra
    Então a confirmação é recusada e o cartão pede para revisar a versão atual
```

### 6. Conformidade com a Constituição
| Artigo | Cumprimento | Exceção? |
|---|---|---|
| II Privacidade | Ações sob `users/{uid}`; `uid` do token | Não |
| IV Confirmação | O que se confirma é exatamente o que está na tela: hash da versão salva conferido na confirmação | Não |
| V Contrato | Endpoints novos no OpenAPI v1, cliente TS regenerado | Não |
| VI Testes | unit, integração, Vitest, evals e AT-F14-01..04 | Não |
| IX Observabilidade | `action_edited` | Não |
| X Acessibilidade | Editor com rótulos, operável por teclado | Não |
| XI Evals | Casos de "Refine with AI" e de respeitar a edição | Não |
| XII Contrato da spec | Edição mantém o `AgentReadySpec` e mostra a prontidão | Não |

---

## Parte C — Validação (Gates 3 e 4)

### 10. Rastreabilidade
| Requisito | Teste(s) | Status |
|---|---|---|
| F14-RF-01 | `test_action_edits_api.py::test_previa_recalcula_sem_gravar`; `ActionCard.test.tsx` (F14-RF-01 Edit/prévia/Save); `e2e/f14-editor.spec.ts` AT-F14-01 | ✅ |
| F14-RF-02 | `test_action_edits_api.py::test_salvar_e_confirmar_cria_o_conteudo_editado`, `test_confirmar_sem_hash_continua_valendo`; AT-F14-01 | ✅ (AT-F14-01 aguarda autorização de escrita no Jira) |
| F14-RF-03 | `test_action_edits_api.py::test_restaurar_volta_a_versao_do_agente`; `test_action_edits_repo.py` (emulador); `ActionCard.test.tsx` (Cancel, Restore); AT-F14-02 | ✅ |
| F14-RF-04 | `test_proposal_tools.py::test_revisar_regrava_a_mesma_acao`, `test_revisar_recusa_proposta_de_outra_conversa_ou_tratada`; `ActionCard.test.tsx` (Refine with AI); evals `f14_v1` (refine); AT-F14-03 | ✅ |
| F14-RF-05 | `test_proposal_tools.py::test_agente_ve_o_titulo_editado_e_le_a_proposta`; evals `f14_v1` (edited_title); AT-F14-03 | ✅ |
| F14-RF-06 | `test_proposal.py`; `SpecEditor.test.tsx` (história, critérios, épico); AT-F14-01 | ✅ |
| F14-RT-01 | `test_action_edits_api.py` (409 na edição e na confirmação); `test_action_edits_repo.py`; `ActionCard.test.tsx` (F14-RT-01); AT-F14-04 | ✅ |
| F14-RT-02 | `test_proposal.py`; `test_action_edits_api.py::test_validacao_igual_a_da_ferramenta` | ✅ |
| F14-RT-03 | `test_action_edits_api.py::test_previa_recalcula_sem_gravar`; `ActionCard.test.tsx` (prévia com debounce, erro de validação) | ✅ |
| F14-RT-04 | `test_proposal.py::test_criterios_renumerados_e_tipo_fixo`; `SpecEditor.test.tsx` (esvaziar mantém a seção) | ✅ |
| F14-RT-05 | `test_action_edits_api.py::test_so_a_dona_edita_e_so_pendente`, `test_expirada_nao_edita`; log `action_edited` | ✅ |

### 11. Evidências
| Data | Versão/commit | Ambiente | Execução (link CI) | Resultado | Aceito por |
|---|---|---|---|---|---|
| 2026-11-27 | `feat/F14-editor-artefatos` | local | — | `make lint` OK; `make test`: backend 799 (cobertura 93,6%), frontend 183; integração no emulador (`test_action_edits_repo.py`) | — |
| 2026-11-27 | idem | local + Vertex | — | Evals `f14_v1`: 5/5, todas as métricas em 100% (`2026-11-27-new-gemini-3.5-flash-lite-f14.json`). Regressão: F19, F20 e F21 em 100%; F05 igual ao go-live exceto `epic_complete` (instabilidade que já existia: sem as ferramentas novas, 3 falhas em 12 repetições dos casos de épico; com elas, 3 em 20) | — |
| 2026-11-27 | idem | local + sandbox (só leitura) | — | AT-F14-02, AT-F14-03 e AT-F14-04 passam com o Gemini real; log da API: 0 `jira_write`, a confirmação da versão antiga recebeu 409 | — |
