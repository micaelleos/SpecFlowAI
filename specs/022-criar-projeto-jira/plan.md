# F22 — O agente cria projetos no Jira — Plano técnico

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

---

## Parte B — Plano técnico (Gate 1)

### Resumo (Summary)
Um novo tipo de ação proposta, `create_project`, que reaproveita a confirmação da F06. A ferramenta do agente valida a chave no Jira e propõe; o `ActionService` executa `POST /rest/api/3/project`, fixa o projeto na conversa sem projeto (F21) e descarta o cache de projetos (F09).

### Contexto técnico (Technical Context)
- **Jira:** `JiraClient` ganha:
  - `validate_project_key(key)`: `GET /rest/api/3/projectvalidate/key`, sem permissão exigida;
  - `suggest_project_key(key)`: `GET /rest/api/3/projectvalidate/validProjectKey`;
  - `create_project(body)`: `POST /rest/api/3/project`, com permissão "Administer Jira" e o `_write` sem repetição.
- **Agente:**
  - `JiraReader` ganha `check_project_key(key) -> str | None`, que devolve a sugestão quando a chave não serve;
  - ferramenta `propor_criacao_projeto` em `agent/tools/project_tools.py`, que entra em todos os toolsets com Jira (`JIRA_TOOLS`).
- **Serviços:** em `services/actions.py`:
  - `_write_project`: o lead é o `accountId` da conexão da proposta;
  - `_done_project`: ação concluída, mensagem de sistema, `pin_project` (transação da F21) e cache descartado.
- **Frontend:** `ActionCard` mostra `create_project` (nome, chave, modelo, responsável, descrição) e, depois de criado, o link "Open in Jira". Depois do Confirm, invalida `jira-projects` e a conversa.

### Conformidade com a Constituição (Constitution Check)
Sem exceção (ver spec §6).

### 7. Desenho
1. **Ferramenta** `propor_criacao_projeto(nome, chave, modelo, descricao)`:
   - confere o formato da chave e do nome;
   - chama `ctx.jira.check_project_key`. Se a chave está em uso ou é inválida, devolve a mensagem com a sugestão e não cria cartão;
   - chama `ctx.actions.propose("create_project", payload, readiness={}, labels=[], preview)`;
   - `payload = {key, name, projectTypeKey, projectTemplateKey, description, assigneeType: "UNASSIGNED"}`;
   - `preview = {project_key, name, template, template_label, description, lead}`; o `lead` é o nome da conta conectada.
2. **Execução:** mesmo fluxo de `confirm` (hash, conexão, claim).
   - `POST` com `{**payload, "leadAccountId": connection.account_id}`;
   - erros:
     - 403 → `jira-project-forbidden` (não repetível);
     - 400 → `jira-project-invalid`, com a mensagem do Jira;
     - incerto → `jira-uncertain`.
3. **Depois de criar:**
   - `result = {issue_key: <KEY>, url: <site>/browse/<KEY>}`, reaproveitando `ActionResult`, sem registro no histórico de issues (F10);
   - mensagem "O usuário confirmou e o SpecFlow criou o projeto KEY (url)";
   - `pin_project(conversation, KEY)`, que só grava se a conversa estiver sem projeto;
   - `delete_projects_cache(uid)`.
4. **Prompt:** uma linha na seção de ferramentas, "Crie projeto só quando o usuário pedir; sugira a chave a partir do nome e use o modelo pedido (padrão Scrum)", em v1 e v2.

### 9. Plano de testes
- **Unit:**
  - cliente com `MockTransport`: validação, sugestão, criação, 403, 400, incerto;
  - ferramenta: chave em uso, formato, modelo, payload e preview;
  - `ActionService`: hash, lead, pin só se vazio, cache descartado, auditoria, 403;
  - prompt: a linha nova está lá.
- **Vitest:** `ActionCard` com `create_project`, pendente e criado.
- **Evals `f22_v1`:** pedido explícito (propõe com modelo e chave), conversa sem projeto pedindo story (não cria projeto) e chave em uso (sugere outra).
- **AT:** AT-F22-01 escreve no Jira sandbox e só roda com `E2E_JIRA_WRITE=1`, autorizado pelo PO; o projeto de teste é apagado à mão depois. AT-F22-02 e AT-F22-03 não criam nada.

### Riscos e rollback
- **Conta sem permissão de administrador:** a mensagem 403 orienta o usuário; nada é criado.
- **Projeto criado em duplicidade:** a escrita não é repetida e a chave é única no Jira.
- **Rollback:** reverter o PR e `make deploy`. Ações `create_project` pendentes passam a ser recusadas na confirmação.

### Gate 1 — Plano aprovado
- [x] Contrato definido antes do código
- [x] Riscos e rollback descritos
- [x] Estimativa cabe na Fase 4 (3 d)
- [x] Conformidade sem exceção
