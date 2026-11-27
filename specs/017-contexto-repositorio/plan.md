# F17 — Contexto do repositório (GitHub, só leitura) — Plano técnico

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

---

## Parte B — Plano técnico (Gate 1)

### Resumo (Summary)
Conexão GitHub por token fine-grained (padrão da F04), vínculo projeto ↔ repositório (padrão da F19) e três ferramentas de leitura para o agente, que só existem no turno com repositório vinculado. A instrução de sistema traz as instruções do repositório e as pastas da raiz (fase Descobrir).

### Contexto técnico (Technical Context)
- **Backend:**
  - `integrations/github/client.py`: `GitHubClient` (httpx, host fixo);
  - `repositories/github.py`: conexões em `users/{uid}/github_connections` e vínculos em `users/{uid}/repo_links/{key}`;
  - `services/github.py`: `GitHubConnectionService` e `RepoLinkService` (`reader_for`);
  - `services/repo_reader.py`: adaptador `RepoReader` para o agente;
  - `agent/tools/repo_tools.py`: `listar_arquivos_do_repositorio`, `buscar_no_repositorio`, `ler_arquivo_do_repositorio`, `repo_note`;
  - `services/chat.py`: `_repo_note` e toolsets `*_repo`;
  - `api/v1/github.py`.
- **Frontend:**
  - Settings: seção "GitHub connection";
  - Projects: "Code repository" por projeto;
  - `ProductApi`: `getGitHubConnection`, `connectGitHub`, `removeGitHubConnection`, `listGitHubRepos`, `getProjectRepo`, `linkProjectRepo`, `unlinkProjectRepo`.
- **Contrato:** OpenAPI e `api-schema.d.ts` regenerados.
- **Infra:** nenhuma mudança (mesma chave KMS, ADR-010).

### Conformidade com a Constituição (Constitution Check)
Sem exceção (ver spec §6).

### 7. Desenho
1. **API**
   - `GET|POST /api/v1/github/connections`, `POST /api/v1/github/connections/{id}/validate`, `DELETE /api/v1/github/connections/{id}` (apaga também os vínculos);
   - `GET /api/v1/github/repos?q=`: repositórios que o token vê (`GET /user/repos`, até 100, filtrados);
   - `GET|PUT|DELETE /api/v1/jira/projects/{key}/repo`: o `PUT` confere o acesso (`GET /repos/{owner}/{repo}`) antes de salvar.
2. **Erros:** `github-invalid-token` (422), `github-unreachable` (502), `github-connection-exists` (409), `github-not-connected` (409), `github-repo-not-found` (404).
3. **Turno do chat:** com projeto e vínculo, `RepoLinkService.reader_for` monta o leitor:
   - instruções: o primeiro de `AGENTS.md`, `CLAUDE.md` e `.github/copilot-instructions.md` (até 6 mil caracteres);
   - pastas e arquivos da raiz pela árvore do branch padrão;
   - `repo_note` entra na instrução de sistema, com o pedido de preencher "Onde mexer" só com caminhos vistos e "Como verificar" com os comandos do repositório.
   - Com 401: conexão inválida, nota "repositório inacessível" e turno sem as ferramentas.
4. **Ferramentas:**
   - `listar_arquivos_do_repositorio(pasta)`: entradas da pasta (até 200), a partir da árvore em cache no turno;
   - `buscar_no_repositorio(texto)`: caminhos da árvore que contêm o texto, depois a busca de código (falha ignorada), até 20;
   - `ler_arquivo_do_repositorio(caminho)`: arquivo ≤ 100 KB, até 12 mil caracteres, ≤ 20 por turno.
   - Tudo em `<dados_repositorio confiavel="nao">`.
5. **Toolsets:** cada toolset ganha a variante `<nome>_repo`; `_toolset` acrescenta o sufixo quando `ctx.repo` existe; `deps.py` compila todas.
6. **Logs:** `github_connected`, `repo_linked`, `repo_unlinked`, `repo_read` (`uid_hash`, contagem de arquivos e buscas; nunca caminhos nem conteúdo).

### 9. Plano de testes
- **Unit:** cliente com `httpx.MockTransport` (cabeçalhos, host fixo, 401/403/404, raw, limite de tamanho), serviços (token nunca no retorno, cifra, vínculo confere acesso, desconectar apaga vínculos), ferramentas (limites, delimitação, cache) e chat (toolset `*_repo`, nota, token recusado).
- **Integração no emulador:** conexão e vínculos gravados sem token em claro; remoção apaga os vínculos.
- **Vitest:** Settings (conectar, erro, remover) e Projects (vincular, desvincular).
- **Evals `f17_v1`:** repositório simulado por caso; métricas `repo_where_to_change`, `repo_paths_exist`, `repo_verify_command` e `repo_injection_resisted`.
- **AT:** AT-F17-01..03 em `e2e/f17-repositorio.spec.ts`, com o token e o repositório do PO (`E2E_GITHUB_TOKEN`, `E2E_GITHUB_REPO`).

### Riscos e rollback
- **Injeção pelo repositório:** conteúdo delimitado, eval de injeção, nenhuma ferramenta de escrita.
- **Limite da busca de código:** a busca pelos caminhos responde sozinha.
- **Rollback:** reverter o PR e `make deploy`. As coleções novas ficam sem uso.

### Gate 1 — Plano aprovado
- [x] Contrato definido antes do código
- [x] Riscos e rollback descritos
- [x] Estimativa cabe na Fase 4 (5 d)
- [x] Conformidade sem exceção
