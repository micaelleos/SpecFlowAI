# ADR-011 — Exportar specs por PR com o mesmo token GitHub (escrita só em branch própria)

- **Status:** Proposto (escolha do PO em 2026-11-27: mesmo token) · **Data:** 2026-11-27
- **Requisitos:** [F18](../../../specs/018-exportar-specs-repositorio/spec.md)
- **Amplia:** ADR-010 (token fine-grained só leitura). **Relacionados:** ADR-003 (ações propostas), ADR-004, ADR-007

## Contexto

A F18 exporta um épico e as histórias dele, criados pelo SpecFlow, como arquivos Spec Kit (`specs/<nnn>-<slug>/spec.md` e
`tasks.md`) num PR no repositório vinculado ao projeto. Para isso é preciso escrever no GitHub, e a ADR-010 previa só leitura.

## Opções

| Opção | Como | Prós | Contras |
|---|---|---|---|
| A. **Mesmo token**, com `Contents: Read and write` e `Pull requests: Read and write` acrescentados pelo usuário | Nada muda na tela; sem a permissão, o cartão avisa | Uma credencial só, padrão da F04/F17 | O token que o agente usa para ler também pode escrever |
| B. Segundo token só para PR | Campo separado em Settings | Separação de privilégios | Dois tokens para criar e renovar |
| C. Sem escrita: baixar os arquivos | O usuário abre o PR à mão | Nenhuma permissão nova | Não atende ao "por PR" |

## Decisão

**Opção A**, com estas garantias no código:

1. **Ação proposta:** abrir o PR é uma ação `create_pull_request` (ADR-003). O cartão mostra o repositório, a branch, os
   arquivos com o conteúdo inteiro e o título do PR. A execução confere o hash do payload exibido.
2. **Só branch própria:** o SpecFlow só cria a branch `specflow/<chave-do-épico>` (com sufixo se já existir), grava nela os
   arquivos do payload e abre o PR para a branch padrão. Nunca escreve na branch padrão, nunca apaga nem força.
3. **As ferramentas de leitura continuam só lendo:** nenhuma ferramenta do agente escreve; a escrita existe só no
   `ActionService`, depois do Confirm.
4. **Sem permissão de escrita (403):** a ação falha com `github-write-forbidden`, que diz quais permissões acrescentar ao token.
5. **Link no Jira (F18-RF-04):** depois do PR, o épico recebe um link remoto para o PR. Se o Jira recusar, o PR fica e o
   aviso aparece no cartão.

## Consequências

- ✅ Nenhuma credencial nova nem infraestrutura nova (Art. VII).
- ⚠️ Com escrita no token, um vazamento permite escrever nos repositórios escolhidos. Mitigação: KMS, token nunca devolvido,
  prazo curto e repositórios restritos no GitHub; a tela de Settings explica as permissões.
- ⚠️ Se o PO quiser separar leitura e escrita, a opção B pode ser acrescentada depois sem mudar o formato da ação.
