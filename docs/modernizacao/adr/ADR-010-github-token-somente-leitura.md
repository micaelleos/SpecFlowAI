# ADR-010 — Contexto do repositório GitHub por token fine-grained, só leitura

- **Status:** Proposto (escolha do PO em 2026-11-27: token fine-grained) · **Data:** 2026-11-27
- **Requisitos:** [F17](../../../specs/017-contexto-repositorio/spec.md)
- **Relacionados:** ADR-003 (ações propostas), ADR-004 (credenciais cifradas por KMS), ADR-007 (spec pronta para agente)

## Contexto

Sem conhecer o código, o agente do SpecFlow não consegue dizer ao agente de código **onde** mexer, e a pesquisa associa a
localização (módulos, arquivos) a mais PRs aceitos (doc 10 §3). A F17 liga um repositório GitHub, em modo leitura, a um
projeto do Jira. O agente lê as instruções do repositório (`AGENTS.md`, `CLAUDE.md`), a árvore de pastas e arquivos
específicos para preencher "Onde mexer" e "Como verificar".

## Opções

| Opção | Acesso | Esforço | Risco |
|---|---|---|---|
| A. **Token fine-grained do usuário** (Contents: read, repositórios escolhidos), cifrado por KMS como o do Jira | Repos públicos e privados que o token vê | Baixo (padrão da F04) | Token de longa duração; o usuário escolhe o prazo |
| B. GitHub App instalado pelo usuário, token de instalação por requisição | Repos onde o App foi instalado | Médio-alto: registro do App, chave privada no Secret Manager, rota de retorno da instalação | Mais peças para operar num projeto de portfólio |
| C. Só repositórios públicos, sem credencial | Só públicos | Mínimo | 60 req/h por IP, compartilhado no Cloud Run; não serve para código privado |

## Decisão

**Opção A.**

1. **Credencial:** token fine-grained com permissão só de leitura (`Contents: read`; `Metadata: read` vem junto),
   restrito aos repositórios que o usuário escolher no GitHub. Validado em `GET /user` e cifrado com a mesma chave KMS
   dos tokens do Jira (ADR-004). Nunca volta na API nem aparece em log; a API mostra só o login e os 4 últimos caracteres.
2. **Host fixo:** o cliente fala só com `https://api.github.com`. Nenhuma URL vem do usuário, então não há SSRF.
   Redirecionamentos não são seguidos.
3. **Vínculo** projeto Jira ↔ repositório em `users/{uid}/repo_links/{projectKey}`: só o nome, o branch padrão e a URL,
   nunca código (Art. II). Desconectar o GitHub apaga a conexão e todos os vínculos.
4. **Leitura limitada e não confiável:**
   - arquivo ≤ 100 KB, devolvido ao modelo com até 12 mil caracteres;
   - até 20 arquivos por turno;
   - busca: primeiro nos caminhos da árvore, que não custa requisição a mais; depois a busca de código do GitHub,
     quando responder. Ela só olha o branch padrão e limita 10 requisições por minuto, então falhar nela não é erro;
   - todo conteúdo volta delimitado como `<dados_repositorio confiavel="nao">`.
5. **Sem escrita:** nenhuma ferramenta escreve no repositório. Exportar specs por PR é a F18, com nova decisão.

## Consequências

- ✅ Mesma experiência da conexão do Jira; nenhuma infraestrutura nova (Art. VII).
- ✅ O usuário controla o alcance do token no próprio GitHub (repositórios e prazo).
- ⚠️ Token de longa duração: se vazar, dá leitura dos repositórios escolhidos até expirar. Mitigação: cifra por KMS,
  token nunca devolvido, prazo curto recomendado na tela.
- ⚠️ Para organizações e vários usuários, um GitHub App (opção B) passa a valer a pena; fica como evolução.
