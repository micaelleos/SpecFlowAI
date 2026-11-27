# F17 — Contexto do repositório (GitHub, só leitura)

| Campo | Valor |
|---|---|
| **Status** | Em implementação |
| **Fase** | 4 — Evolução |
| **Responsável** | PO |
| **Dependências** | F05, F09, F12 |
| **ADRs relacionados** | ADR-004, ADR-007, ADR-010 |
| **Estimativa** | 5 dias |

> [Spec](spec.md) · [Plano](plan.md) · [Tarefas](tasks.md) · [Roadmap](../ROADMAP.md) · [Doc 10 — Specs para agentes](../../docs/modernizacao/10-specs-para-agentes.md)

**Revisão 2026-11-27 (contra o código, antes da implementação; PO escolheu a F17):**
- **Credencial:** token fine-grained só de leitura, cifrado por KMS como o do Jira (escolha do PO; ADR-010), no lugar do GitHub App. A chave no Secret Manager deixou de existir (era o F17-RT-01 antigo).
- **Vínculo:** na tela Projects, como o do Confluence (F19), em `users/{uid}/repo_links/{key}`.
- **Busca:** primeiro nos caminhos da árvore; depois a busca de código do GitHub, quando responder. Ela só olha o branch padrão e limita 10 requisições por minuto.
- **Repositório de exemplo do AT:** um repositório real que o PO escolher, no lugar do "projeto E2E".

---

## Parte A — Especificação (Gate 0)

### 1. Contexto e objetivo
- **Problema:** sem conhecer o código, o agente do SpecFlow não consegue dizer ao agente de código **onde** mexer, e a pesquisa associa a localização (módulos, arquivos) a mais PRs aceitos (doc 10 §3).
- **Objetivo:** o PO conecta o GitHub com um token só de leitura e vincula um repositório a cada projeto do Jira. O agente usa as instruções do repositório (`AGENTS.md`, `CLAUDE.md`), a estrutura de pastas e os arquivos para preencher "Onde mexer" e "Como verificar" e respeitar as convenções do projeto.
- **Indicador de sucesso:** % de specs com "Onde mexer" preenchida em projetos com repositório; caminhos citados que existem no repositório (evals).

### 2. Escopo
- **Dentro:**
  - conexão GitHub por token fine-grained (validar, guardar cifrado, testar, remover);
  - vínculo projeto ↔ repositório na tela Projects;
  - leitura pelo agente: instruções do repositório, árvore de pastas, busca e leitura de arquivo, com limites;
  - "Onde mexer" e "Como verificar" a partir do repositório.
- **Fora:**
  - escrever no repositório (a F18 cria PR só com specs);
  - GitHub App, GitLab e Bitbucket;
  - indexação vetorial;
  - branches além do padrão.

### 3. Requisitos funcionais
| ID | Requisito | Prioridade |
|---|---|---|
| F17-RF-01 | O PO conecta o GitHub com um token fine-grained só de leitura (validado antes de guardar) e vincula um repositório que o token vê a cada projeto do Jira, na tela Projects | Must |
| F17-RF-02 | Numa conversa de projeto com repositório vinculado, o agente recebe as instruções do repositório (`AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`) e as pastas da raiz, e pode listar pastas, buscar e ler arquivos | Must |
| F17-RF-03 | A seção "Onde mexer" lista arquivos ou módulos que existem no repositório, com o motivo de cada um, e "Como verificar" usa os comandos de teste do repositório | Must |
| F17-RF-04 | O PO desvincula o repositório de um projeto ou remove a conexão GitHub (o que apaga todos os vínculos); o SpecFlow não guarda cópia do código | Must |
| F17-RF-05 | Sem repositório vinculado, ou com o token recusado, a conversa segue sem as ferramentas do repositório; token recusado marca a conexão como inválida | Must |

### 4. Requisitos técnicos / não funcionais
| ID | Requisito | Verificação |
|---|---|---|
| F17-RT-01 | O token é cifrado por KMS (ADR-004) e nunca volta na API nem aparece em log; a API mostra só o login e os 4 últimos caracteres | unit + integração |
| F17-RT-02 | Cliente só com `https://api.github.com`, sem seguir redirecionamentos, com timeout e cabeçalhos fixos | unit |
| F17-RT-03 | Leitura limitada: arquivo ≤ 100 KB (até 12 mil caracteres ao modelo), ≤ 20 arquivos por turno, busca ≤ 20 resultados; conteúdo delimitado como dado não confiável | unit + eval de injeção |
| F17-RT-04 | Nenhum conteúdo de código persistido: só conexão e vínculos em `users/{uid}`; o código aparece apenas nas mensagens do turno | integração |
| F17-RT-05 | As ferramentas do repositório só existem no turno com repositório vinculado (toolsets `*_repo`) | unit |

### 5. Teste final de aceitação
```gherkin
Funcionalidade: Contexto do repositório

  Cenário: AT-F17-01 "Onde mexer" a partir do repositório         # F17-RF-01, F17-RF-02, F17-RF-03
    Dado o GitHub conectado e o repositório de exemplo vinculado ao projeto do sandbox
    Quando peço uma story que mexe num módulo do repositório
    Então a spec proposta tem "Onde mexer" citando arquivos que existem no repositório
    E "Como verificar" cita um comando de teste do repositório

  Cenário: AT-F17-02 Desvincular                                  # F17-RF-04, F17-RF-05
    Dado o repositório vinculado ao projeto
    Quando desvinculo o repositório
    Então a próxima conversa do projeto não lê o repositório

  Cenário: AT-F17-03 Token recusado                               # F17-RF-01, F17-RT-01
    Quando informo um token inválido
    Então a conexão não é salva e vejo "GitHub rejected the token"
```

### 6. Conformidade com a Constituição
| Artigo | Cumprimento | Exceção? |
|---|---|---|
| II Privacidade | Conexão e vínculos sob `users/{uid}`; nenhum código guardado | Não |
| III Segredos | Token cifrado por KMS, nunca devolvido nem logado | Não |
| IV Confirmação | Só leitura no GitHub; nada é escrito | Não |
| V Contrato | Endpoints novos no OpenAPI v1, cliente TS regenerado | Não |
| VI Testes | unit, integração, Vitest, evals e AT-F17-01..03 | Não |
| VII Simplicidade | Sem infraestrutura nova (mesma chave KMS) | Não |
| IX Observabilidade | Logs `github_connected`, `repo_linked`, `repo_read` sem conteúdo | Não |
| XI Evals | `f17_v1`: "Onde mexer" com caminhos reais, comando de teste, injeção no `AGENTS.md` | Não |
| XII Contrato da spec | "Onde mexer" preenchida com contexto real melhora a prontidão | Não |

---

## Parte C — Validação (Gates 3 e 4)

### 10. Rastreabilidade
| Requisito | Teste(s) | Status |
|---|---|---|
| F17-RF-01 | — | ⏳ |
| F17-RF-02 | — | ⏳ |
| F17-RF-03 | — | ⏳ |
| F17-RF-04 | — | ⏳ |
| F17-RF-05 | — | ⏳ |

### 11. Evidências
| Data | Versão/commit | Ambiente | Execução (link CI) | Resultado | Aceito por |
|---|---|---|---|---|---|
