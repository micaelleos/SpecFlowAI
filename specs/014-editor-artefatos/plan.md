# F14 — Editor de artefatos antes da exportação — Plano técnico

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

---

## Parte B — Plano técnico (Gate 1)

### Resumo (Summary)
Serviço `ActionEditService`, com prévia, salvar e restaurar, sobre as mesmas funções de payload, prévia e prontidão das ferramentas do agente. Três endpoints novos em `/api/v1/actions/{id}`, e a confirmação passa a conferir o hash visto. O `ActionCard` ganha modo de edição por seção. O agente ganha `ler_proposta` e `revisar_proposta` para o "Refine with AI".

### Contexto técnico (Technical Context)
- **Backend:**
  - `agent/spec/proposal.py` (nova): extração de `_preview`, `labels` e payload das ferramentas, usada pela ferramenta e pelo serviço;
  - `services/action_edits.py` (nova);
  - `repositories/actions.py`: `save_version` transacional;
  - `api/v1/actions.py`;
  - `agent/tools/jira_tools.py`: `ler_proposta` e `revisar_proposta`;
  - `services/chat.py`: `actions_note` com "editada pelo usuário".
- **Frontend:**
  - `components/SpecEditor.tsx` (nova);
  - `components/ActionCard.tsx`;
  - `product/types.ts`, `product/http.ts`, `product/actions.ts`, `product/demo.ts`;
  - `i18n/en.ts`.
- **Contrato:** OpenAPI e `api-schema.d.ts` regenerados (`make api-types`).

### Conformidade com a Constituição (Constitution Check)
Sem exceção (ver spec §6).

### 7. Desenho
1. **Dados da ação (`users/{uid}/pending_actions/{id}`):** campos novos
   - `spec` na resposta da API (`ActionOut.spec`), só para os tipos editáveis, para o editor partir dela;
   - `version` (1 na proposta);
   - `editedBy` (`agent` | `user`);
   - `agentVersion` ({payload, payloadHash, preview, readiness, labels}), gravado na primeira edição do usuário e atualizado quando o agente revisa.
2. **`POST /api/v1/actions/{id}/preview`** {spec, priority?}: valida com o `TypeAdapter(AgentReadySpec)`, mantém o tipo da proposta (422 se mudar) e devolve {preview, readiness, labels}. Não grava.
3. **`PUT /api/v1/actions/{id}/spec`** {spec, priority?, base_hash}:
   - na mesma transação, confere que a ação é da pessoa, está `pending`, não expirou e tem `payloadHash == base_hash`;
   - refaz payload, hash, prévia, prontidão e labels; numa atualização, mantém as labels que não são do SpecFlow e o `before` lido na proposta;
   - grava `version+1` e `editedBy=user` e registra o log `action_edited`;
   - devolve o `ActionOut`. Conflito: 409 `action-changed`.
4. **`POST /api/v1/actions/{id}/restore`** {base_hash}: volta ao `agentVersion`, com as mesmas regras.
5. **Confirmação:** `POST …/confirm` aceita `{payload_hash}` opcional. Diferente do atual: 409 `action-changed`, antes de qualquer escrita.
6. **Agente:**
   - `ler_proposta(action_id)` devolve a spec atual (JSON) de uma ação pendente desta conversa, com a marca de editada;
   - `revisar_proposta(action_id, spec | epic_spec, priority?)` regrava pela mesma função do serviço (`editedBy=agent`, atualiza `agentVersion`);
   - o `ActionSink` ganha `read` e `revise`, com adaptador em `services/` (o agente não importa repositório);
   - `actions_note` mostra o título atual e "(editada pelo usuário)".
7. **Tela:**
   - "Edit" no cartão pendente com spec abre o `SpecEditor`: campos por seção, listas com um item por linha e critérios como blocos com Dado/Quando/Então;
   - a prévia e a prontidão vêm do `/preview`, com debounce de 400 ms;
   - "Save", "Cancel" e, quando `editedBy=user`, "Restore agent version";
   - "Refine with AI" na seção abre um campo de instrução e envia ao chat "Refine the section "<seção>" of proposal <id>: <instrução>";
   - "Confirm" manda o hash da versão mostrada.

### 9. Plano de testes
- **Unit:** `test_action_edits.py` (prévia, salvar, conflito, restaurar, tipo trocado, expirada, outra pessoa, labels da atualização), confirmação com hash, ferramentas `ler_proposta`/`revisar_proposta` e `actions_note`.
- **Integração:** `save_version` transacional no emulador.
- **Vitest:** `SpecEditor.test.tsx` (seções, critérios, prévia com debounce, Save, Cancel, Restore) e `ActionCard.test.tsx` (Confirm com hash, 409).
- **Evals:** `evals/datasets/f14_v1.jsonl`, com refinar uma seção sem perder a edição e responder o título editado.
- **AT:** AT-F14-01..04 em `e2e/f14-editor.spec.ts` (local + sandbox do Jira para o 01).

### Riscos e rollback
- **Confirmar o que não se vê:** coberto pelo hash na confirmação e pelo 409.
- **Edição que quebra o esquema:** a API valida igual à ferramenta; o editor não deixa salvar com erro de validação.
- **Rollback:** reverter o PR e `make deploy`. As ações já editadas continuam válidas, porque o payload tem o mesmo formato.

### Gate 1 — Plano aprovado
- [x] Contrato definido antes do código
- [x] Riscos e rollback descritos
- [x] Estimativa cabe na Fase 4 (6 d)
- [x] Conformidade sem exceção
