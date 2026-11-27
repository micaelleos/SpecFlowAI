# F17 — Contexto do repositório (GitHub, só leitura) — Tarefas

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

**Entradas:** plan.md, spec.md, ADR-010

## Formato: `- [ ] Tnnn [P?] [Fxx-RF-nn?] Descrição em caminho/do/arquivo — teste: <teste> — <est.>`

**Total:** 9 tarefas · ≈ 5 d

## 8. Tarefas

### Fase 1: Fundação

- [ ] T001 [F17-RF-01] `GitHubClient` (host fixo, raw, limites, erros) em backend/app/integrations/github/client.py — teste: backend/tests/unit/test_github_client.py — 0,5 d
- [ ] T002 [F17-RF-01] [F17-RF-04] Repositórios e `GitHubConnectionService`/`RepoLinkService` em backend/app/repositories/github.py e backend/app/services/github.py — teste: backend/tests/unit/test_github_service.py, backend/tests/integration/test_github_repo.py — 1 d
- [ ] T003 [F17-RF-01] Rotas `/api/v1/github/*` e `/api/v1/jira/projects/{key}/repo`; OpenAPI e cliente TS — teste: backend/tests/unit/test_github_api.py — 0,5 d

### Fase 2: Agente

- [ ] T004 [F17-RF-02] [F17-RF-03] Leitor e ferramentas do repositório, `repo_note`, em backend/app/agent/tools/repo_tools.py e backend/app/services/repo_reader.py — teste: backend/tests/unit/test_repo_tools.py — 1 d
- [ ] T005 [F17-RF-05] Chat: `_repo_note`, toolsets `*_repo`, token recusado — teste: backend/tests/unit/test_chat_repo.py — 0,5 d

### Fase 3: Tela

- [ ] T006 [F17-RF-01] [F17-RF-04] Settings "GitHub connection" e Projects "Code repository" — teste: frontend/src/pages/*.test.tsx — 0,75 d

### Fase 4: Validação

- [ ] T007 Evals `f17_v1` e F05/F14/F19/F20/F21 sem regressão — teste: `evals/run.py` — 0,5 d
- [ ] T008 AT-F17-01..03 em frontend/e2e/f17-repositorio.spec.ts — teste: Playwright — 0,25 d
- [ ] T009 Rastreabilidade, evidências, CLAUDE.md — teste: `make trace` — 0,1 d
