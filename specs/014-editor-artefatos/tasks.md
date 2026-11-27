# F14 — Editor de artefatos antes da exportação — Tarefas

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

**Entradas:** plan.md, spec.md

## Formato: `- [ ] Tnnn [P?] [Fxx-RF-nn?] Descrição em caminho/do/arquivo — teste: <teste> — <est.>`

**Total:** 10 tarefas · ≈ 6 d

## 8. Tarefas

### Fase 1: Contrato e fundação

- [x] T001 [F14-RF-06] Extrair prévia, labels e payload das ferramentas para backend/app/agent/spec/proposal.py (sem mudar o comportamento) — teste: backend/tests/unit/test_proposal.py e os testes das ferramentas — 0,5 d
- [x] T002 [F14-RF-01] `ActionEditService.preview/save/restore` em backend/app/services/action_edits.py e `save_version` transacional em backend/app/repositories/actions.py — teste: backend/tests/unit/test_action_edits.py, backend/tests/integration/test_action_edits_repo.py — 1 d
- [x] T003 [F14-RF-02] Endpoints `preview`, `spec`, `restore`, `ActionOut.spec/version/edited_by` e `payload_hash` na confirmação em backend/app/api/v1/actions.py; OpenAPI e cliente TS — teste: backend/tests/unit/test_action_edits_api.py — 0,5 d

### Fase 2: Agente

- [x] T004 [F14-RF-05] `actions_note` com título atual e "editada pelo usuário"; ferramenta `ler_proposta` — teste: backend/tests/unit/test_proposal_tools.py — 0,5 d
- [x] T005 [F14-RF-04] Ferramenta `revisar_proposta` (mesma ação, `editedBy=agent`) — teste: backend/tests/unit/test_proposal_tools.py — 0,5 d

### Fase 3: Tela

- [x] T006 [F14-RF-06] `SpecEditor` por seção (história/tarefa e épico) em frontend/src/components/SpecEditor.tsx — teste: frontend/src/components/SpecEditor.test.tsx — 1 d
- [x] T007 [F14-RF-01] [F14-RF-03] Modo de edição no `ActionCard`: prévia ao vivo, Save, Cancel, Restore; Confirm com hash e 409 — teste: frontend/src/components/ActionCard.test.tsx — 0,5 d
- [x] T008 [F14-RF-04] "Refine with AI" por seção envia a instrução ao chat — teste: frontend/src/components/ActionCard.test.tsx — 0,25 d

### Fase 4: Validação

- [x] T009 Evals `f14_v1` (refinar sem perder a edição; título editado) e F05/F19/F20/F21 sem regressão — teste: `evals/run.py` — 0,5 d
- [x] T010 AT-F14-01..04 (AT-F14-01 escreve no Jira: roda com E2E_JIRA_WRITE=1 depois da autorização do PO) em frontend/e2e/f14-editor.spec.ts, rastreabilidade e evidências — teste: Playwright, `make trace` — 0,75 d
