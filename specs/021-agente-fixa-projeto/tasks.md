# F21 — O agente fixa o projeto da conversa — Tarefas

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

**Entradas:** plan.md, spec.md

## Formato: `- [ ] Tnnn [P?] [Fxx-RF-nn?] Descrição em caminho/do/arquivo — teste: <teste> — <est.>`

**Total:** 7 tarefas · ≈ 2,5 d

## 8. Tarefas

### Fase 1: Fundação

- [ ] T001 [F21-RF-03] `pin_project` transacional no `ChatStore` (backend/app/repositories/chat.py ou equivalente) e `MemoryChatStore` — teste: backend/tests/integration/test_pin_project.py — 0,25 d
- [ ] T002 [F21-RF-01] `ConversationPinner`, `ToolContext.pinner/pinned` e a ferramenta `fixar_projeto_da_conversa` em backend/app/agent/tools/conversation_tools.py — teste: backend/tests/unit/test_conversation_tools.py — 0,25 d

### Fase 2: Turno

- [ ] T003 [F21-RF-02] Toolset `jira_pin` e continuação do turno depois da fixação em backend/app/services/chat.py, log `conversation_pinned` — teste: backend/tests/unit/test_chat_pin.py — 0,5 d
- [ ] T004 [F21-RF-01] Prompt v2 e `NO_PROJECT_NOTE` mandam fixar quando o usuário nomeia o projeto — teste: backend/tests/unit/test_chat_pin.py, evals `pin_*` — 0,25 d

### Fase 3: Tela

- [ ] T007 [F21-RF-05] Seletor "Pin a project" no topo do chat sem projeto em frontend/src/pages/ChatPage.tsx — teste: frontend/src/pages/ChatPage.test.tsx — 0,5 d

### Fase 4: Validação

- [ ] T005 [F21-RF-04] [F21-RF-05] AT-F21-01..04 em frontend/e2e/f21-fixar-projeto.spec.ts (sandbox) — teste: Playwright — 0,5 d
- [ ] T006 Evals F05/F19/F20 sem regressão, rastreabilidade e evidências — teste: `evals/run.py --compare`, `make trace` — 0,25 d
