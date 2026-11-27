# F21 — O agente fixa o projeto da conversa — Plano técnico

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md)

---

## Parte B — Plano técnico (Gate 1)

### Resumo (Summary)
Ferramenta nova `fixar_projeto_da_conversa`, oferecida só em conversa sem projeto. Ela grava `projectKey` por uma interface injetada. Depois dela, o `ChatService` interrompe a execução do grafo e continua o mesmo turno com a instrução e as ferramentas do projeto.

### Contexto técnico (Technical Context)
- **Backend:** `agent/tools/conversation_tools.py` (nova), `agent/tools/context.py` (`ConversationPinner`, `ToolContext.pinner` e `pinned`), `services/chat.py` (toolset `jira_pin` e continuação), `repositories/conversations.py` ou o `ChatStore` (`pin_project` transacional).
- **Frontend:** o chip aparece sem mudança, porque a lista de conversas já é relida no `done` (`useChatStream.ts`). Pin manual: seletor "Pin a project" em `pages/ChatPage.tsx`, com os projetos de `ProductApi.listProjects` e o mesmo `PATCH` do × (F07).
- **Testes:** `ScriptedChatModel`, `MemoryChatStore`, emulador do Firestore, Playwright no sandbox.

### Conformidade com a Constituição (Constitution Check)
Sem exceção (ver spec §6).

### 7. Desenho
1. **Toolset:** `jira_pin` = `JIRA_TOOLS` + `fixar_projeto_da_conversa`, escolhido quando a conversa não tem projeto e o Jira está conectado. Com projeto, os toolsets da F19/F20 não têm a ferramenta (F21-RF-03).
2. **Ferramenta:**
   - valida a chave contra `ctx.jira.list_projects()` (cache do turno);
   - chama `ctx.pinner.pin(key)`;
   - grava `ctx.pinned = key`;
   - devolve "Conversa fixada no projeto X". Uma segunda chamada no turno é recusada.
3. **Pinner:** `ChatService` injeta um adaptador que chama `ChatStore.pin_project(uid, conversation_id, key)`. A gravação acontece numa transação: só grava se `projectKey` estiver vazio, e senão devolve o projeto atual (a ferramenta recusa).
4. **Continuação (F21-RF-02):**
   - no laço do `astream`, as mensagens novas do turno são acumuladas;
   - quando chega o `ToolMessage` de `fixar_projeto_da_conversa` com `ctx.pinned`, o laço para e o gerador é fechado;
   - o serviço monta a instrução de novo com `project_note` e `_docs_note(ctx.pinned)`, que preenche `ctx.confluence`, `docs_writer` ou `space_creator`, e escolhe o toolset;
   - em seguida roda o agente com `[System novo, *janela, Human, *mensagens do turno]`; a última mensagem é a resposta da ferramenta, o que o Gemini aceita;
   - `iterations` continua de onde parou.
5. **Log:** `conversation_pinned` (`uid_hash`, `project_key`).
6. **Pin manual (F21-RF-05):** numa conversa existente sem projeto, um `<select>` com rótulo "Pin a project" lista os projetos da conexão Jira; ao escolher, `updateConversation(id, {projectKey})` e as conversas são relidas. Conversa nova (`/chat` sem id) usa o mesmo seletor para definir o projeto antes da 1ª mensagem (`projeto` na URL).
7. **Instrução:** o `NO_PROJECT_NOTE` (só com Jira conectado e conversa sem projeto) manda usar a ferramenta quando o usuário nomeia o projeto. O `system_v2.md` não muda: uma linha a mais nele piorou os casos sem Jira nas evals.

### 9. Plano de testes
- **Unit:** a ferramenta (fixa, recusa chave desconhecida, recusa a segunda vez, recusa conversa já fixada) e a continuação com `ScriptedChatModel` (fixa e propõe página no mesmo turno; o índice do espaço vai na 2ª instrução).
- **Integração:** `pin_project` transacional no emulador (não sobrescreve).
- **Evals:** 3 casos novos (`pin_*`) no conjunto da F05.
- **Vitest:** seletor aparece só sem projeto, fixa ao escolher, some com projeto (`ChatPage.test.tsx`).
- **AT:** AT-F21-01..04 em `e2e/f21-fixar-projeto.spec.ts` (sandbox, Gemini real).

### Riscos e rollback
- **Fixar o projeto errado:** o prompt só manda fixar quando o usuário nomeia o projeto ou confirma, e o × da tela desfaz.
- **Continuação quebrar o turno:** coberta por teste; se falhar, o erro é o do turno (`llm-unavailable`), e o projeto fica fixado para a próxima mensagem.
- **Rollback:** reverter o PR e `make deploy`.

### Gate 1 — Plano aprovado
- [x] Contrato definido antes do código
- [x] Riscos e rollback descritos
- [x] Estimativa cabe na Fase 4 (2,5 d)
- [x] Conformidade sem exceção
