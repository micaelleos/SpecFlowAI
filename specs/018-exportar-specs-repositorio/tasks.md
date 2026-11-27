# F18 — Exportar specs para o repositório — Tarefas

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

**Entradas:** plan.md, spec.md, ADR-011

## Formato: `- [x] Tnnn [P?] [Fxx-RF-nn?] Descrição em caminho/do/arquivo — teste: <teste> — <est.>`

**Total:** 8 tarefas · ≈ 4 d

## 8. Tarefas

- [x] T001 [F18-RF-02] Escrita no `GitHubClient` (refs, contents, pulls) e `add_remote_link` no `JiraClient` — teste: backend/tests/unit/test_github_write.py — 0,5 d
- [x] T002 [F18-RF-03] `render_files` (spec.md e tasks.md) em backend/app/services/spec_export.py — teste: backend/tests/unit/test_spec_export.py — 0,5 d
- [x] T003 [F18-RF-01] [F18-RF-05] `RepoSpecExporter` (histórico F10, pasta e branch livres) — teste: backend/tests/unit/test_spec_export.py — 0,75 d
- [x] T004 [F18-RF-01] [F18-RF-05] Ferramenta `propor_exportacao_para_repositorio` e ligação no chat — teste: backend/tests/unit/test_export_tools.py — 0,5 d
- [x] T005 [F18-RF-02] [F18-RF-04] Execução `create_pull_request` no `ActionService` — teste: backend/tests/unit/test_export_actions.py — 0,75 d
- [x] T006 [F18-RF-01] Cartão do PR e "Export to repository" em Created issues — teste: frontend/src/components/ActionCard.test.tsx, frontend/src/pages/IssuesPage.test.tsx — 0,5 d
- [x] T007 Evals `f18_v1` e regressão — teste: `evals/run.py` — 0,25 d
- [x] T008 AT-F18-01..03, rastreabilidade, evidências, CLAUDE.md — teste: Playwright, `make trace` — 0,25 d
