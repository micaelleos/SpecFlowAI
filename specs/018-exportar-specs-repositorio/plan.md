# F18 — Exportar specs para o repositório — Plano técnico

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

---

## Parte B — Plano técnico (Gate 1)

### Resumo (Summary)
Uma ação proposta nova, `create_pull_request`. A ferramenta `propor_exportacao_para_repositorio(chave_do_epico)` existe só nos toolsets `*_repo` (F17). Ela pede ao `SpecExporter` o rascunho, que lê o histórico da F10 e as specs guardadas, monta os arquivos e escolhe a pasta e a branch livres. O `ActionService` executa a ação depois do Confirm.

### Contexto técnico (Technical Context)
- **GitHub (`integrations/github/client.py`):** `branch_sha`, `create_branch`, `put_file`, `create_pull`, todos com escrita sem repetição.
- **Jira:** `JiraClient.add_remote_link(key, url, title)`.
- **Agente:**
  - `agent/tools/export_tools.py`: ferramenta `propor_exportacao_para_repositorio`;
  - `ctx.spec_exporter`: Protocol `SpecExporter` em `context.py`.
- **Serviços:**
  - `services/spec_export.py`: `RepoSpecExporter` monta o rascunho com `render.to_markdown`; `render_files` é pura e testável;
  - `ActionService._execute_pull_request`.
- **Frontend:**
  - cartão do PR em `ActionCard`: repositório, branch, arquivos em `<details>`;
  - "Export to repository" nos épicos de Created issues.

### Conformidade com a Constituição (Constitution Check)
Sem exceção (ver spec §6).

### 7. Desenho
1. **Rascunho** (`RepoSpecExporter.draft(epic_key)`):
   - o épico tem de estar no histórico com `specActionId` e tipo épico; as histórias são as ações `create_issue` concluídas com `parent_key == epic_key`;
   - pasta: o próximo `nnn` livre em `specs/` da árvore do repositório (`001` se não existir), mais o slug do título (até 40 caracteres);
   - branch: `specflow/<chave-minúscula>`, com sufixo `-2`, `-3` e assim por diante enquanto existir na árvore de refs (`GET /git/ref/heads/...`);
   - `payload = {repo, base, branch, title, body, files: [{path, content}], epic_key, issue_keys}`;
   - `preview = {repo, base, branch, title, files: [{path, content}], epic_key, issue_keys, jira_link: true}`.
2. **Execução** (`create_pull_request`):
   - confere o hash e a conexão GitHub válida;
   - `branch_sha(base)`, `create_branch(branch, sha)`, `put_file` de cada arquivo (mensagem `docs(spec): <epic> via SpecFlow`) e `create_pull`;
   - depois, `add_remote_link` no épico. Uma falha nesse passo vira aviso, não falha da ação.
   - Erros:
     - 403 → `github-write-forbidden`;
     - 422 na branch → `github-branch-exists`;
     - 401 → conexão inválida;
     - incerto → `github-uncertain`.
   - Resultado: `{issue_key: "#<n>", url}`, com uma mensagem de sistema com o link.
3. **Formato** (`render_files`):
   - `spec.md`:
     - cabeçalho com tabela (Status "Rascunho", origem SpecFlow, épico com link);
     - "Parte A — Especificação" com o épico (`to_markdown`);
     - "Histórias", com uma subseção `### <KEY> — <título>` por história (`to_markdown`, com cabeçalhos rebaixados);
     - "Rastreabilidade", com uma tabela de CA por história.
   - `tasks.md`: `- [ ] T001 [<KEY>] <título> — critérios: CA-01..CA-nn`.
4. **Logs:** `github_write`, com `uid_hash`, `action_id`, `repo`, `pr`, `result` e `code`.

### 9. Plano de testes
- **Unit:**
  - cliente com `MockTransport`: refs, contents, pulls, 403, 422, sem repetir;
  - `render_files`: seções, CA e tarefas;
  - exporter: pasta seguinte, branch com sufixo, épico ausente, histórias de outro épico;
  - ferramenta: sem repositório, sem épico, propõe;
  - `ActionService`: hash, ordem das chamadas, link no Jira, aviso, 403.
- **Vitest:** cartão `create_pull_request` e botão em Created issues.
- **Evals `f18_v1`:** exporta quando pedido (chave certa), não exporta sem pedido.
- **AT:** AT-F18-01 escreve no GitHub e no Jira e só roda com `E2E_GITHUB_WRITE=1`, autorizado pelo PO. AT-F18-02 e AT-F18-03 não escrevem.

### Riscos e rollback
- **Escrita na branch padrão:** impossível pelo código; a branch do payload começa por `specflow/` e é diferente de `base`, conferido também na execução.
- **PR duplicado:** a escrita não é repetida; uma branch que já existe muda o sufixo na proposta.
- **Rollback:** reverter o PR e `make deploy`. PRs já abertos ficam no GitHub para o time fechar.

### Gate 1 — Plano aprovado
- [x] Contrato definido antes do código
- [x] Riscos e rollback descritos
- [x] Estimativa cabe na Fase 4 (4 d)
- [x] Conformidade sem exceção
