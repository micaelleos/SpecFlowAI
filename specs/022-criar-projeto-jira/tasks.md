# F22 — O agente cria projetos no Jira — Tarefas

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

**Entradas:** plan.md, spec.md

## Formato: `- [x] Tnnn [P?] [Fxx-RF-nn?] Descrição em caminho/do/arquivo — teste: <teste> — <est.>`

**Total:** 7 tarefas · ≈ 3 d

## 8. Tarefas

- [x] T001 [F22-RF-02] `validate_project_key`, `suggest_project_key` e `create_project` em backend/app/integrations/jira/client.py — teste: backend/tests/unit/test_jira_project_create.py — 0,5 d
- [x] T002 [F22-RF-01] [F22-RF-02] Ferramenta `propor_criacao_projeto` e `check_project_key` em backend/app/agent/tools/project_tools.py e backend/app/services/jira_reader.py — teste: backend/tests/unit/test_project_tools.py — 0,5 d
- [x] T003 [F22-RF-03] [F22-RF-04] Execução `create_project`, pin e cache em backend/app/services/actions.py — teste: backend/tests/unit/test_project_actions.py — 0,75 d
- [x] T004 [F22-RF-05] Prompt v1/v2 e OpenAPI — teste: backend/tests/unit/test_project_tools.py — 0,25 d
- [x] T005 [F22-RF-01] Cartão `create_project` em frontend/src/components/ActionCard.tsx — teste: frontend/src/components/ActionCard.test.tsx — 0,5 d
- [x] T006 Evals `f22_v1` e F05/F21 sem regressão — teste: `evals/run.py` — 0,25 d
- [x] T007 AT-F22-01..03, rastreabilidade, evidências, CLAUDE.md — teste: Playwright, `make trace` — 0,25 d
