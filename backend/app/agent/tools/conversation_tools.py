"""Fixar o projeto da conversa (F21).

Só existe numa conversa sem projeto e com o Jira conectado (o `ChatService` injeta o `pinner`).
O agente fixa uma vez e não troca nem solta: a troca é pelo botão de soltar no topo do chat
ou numa conversa nova.
"""

from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from pydantic import Field

from app.agent.tools.context import tool_context
from app.agent.tools.jira_tools import _projects

PIN_TOOL = "fixar_projeto_da_conversa"
PROGRESS = {PIN_TOOL: "Fixando o projeto da conversa…"}
NOT_AVAILABLE = (
    "Esta conversa já tem projeto fixado (ou o Jira não está conectado): você não troca nem solta "
    "o projeto. Para outro projeto, o usuário solta pelo botão \u00d7 no topo do chat ou abre uma "
    "conversa nova."
)


@tool(PIN_TOOL)
async def fixar_projeto_da_conversa(
    chave_do_projeto: Annotated[str, Field(min_length=1, max_length=20)], config: RunnableConfig
) -> str:
    """Fixa ESTA conversa num projeto do Jira do usuário. Use só quando o usuário nomear o projeto
    (ou confirmar a sua sugestão) numa conversa sem projeto. Depois de fixar, a resposta segue com
    o contexto do projeto, incluindo a documentação do Confluence vinculada. Não existe como trocar
    ou soltar o projeto depois."""
    ctx = tool_context(config)
    if ctx.pinner is None or ctx.jira is None or ctx.pinned is not None:
        return NOT_AVAILABLE
    key = chave_do_projeto.strip().upper()
    projects = await _projects(ctx)
    known = {p.key: p.name for p in projects}
    if key not in known:
        options = ", ".join(f"{k} ({n})" for k, n in sorted(known.items())) or "nenhum"
        return (
            f"O projeto {key} não está entre os projetos que a conta do usuário vê no Jira. "
            f"Nada foi fixado. Projetos disponíveis: {options}. Pergunte qual é o certo."
        )
    current = await ctx.pinner.pin(key)
    if current is None:
        return "A conversa não foi encontrada; nada foi fixado."
    if current != key:
        return f"A conversa já estava fixada no projeto {current}. {NOT_AVAILABLE}"
    ctx.pinned = key
    return f"Conversa fixada no projeto {key} ({known[key]}). Siga com o pedido do usuário."


PIN_TOOLS: list[BaseTool] = [fixar_projeto_da_conversa]
