"""Criar projeto no Jira por ação proposta (F22, ADR-003).

A ferramenta só valida e propõe: o projeto é criado depois do Confirm, com o mesmo payload
(F22-RT-01). Modelos numa lista fechada de projetos *company-managed* (F22-RT-02).
"""

import re
from typing import Annotated, Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from pydantic import Field

from app.agent.tools.context import JiraToolError, tool_context

KEY = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")
Template = Literal["scrum", "kanban", "negocio"]
# modelo → (projectTypeKey, projectTemplateKey, rótulo do cartão)
TEMPLATES: dict[str, tuple[str, str, str]] = {
    "scrum": ("software", "com.pyxis.greenhopper.jira:gh-simplified-scrum-classic", "Scrum"),
    "kanban": ("software", "com.pyxis.greenhopper.jira:gh-simplified-kanban-classic", "Kanban"),
    "negocio": (
        "business",
        "com.atlassian.jira-core-project-templates:jira-core-simplified-task-tracking",
        "Tarefas (negócio)",
    ),
}
PROGRESS = {"propor_criacao_projeto": "Preparando o projeto…"}


@tool
async def propor_criacao_projeto(
    nome: Annotated[str, Field(min_length=2, max_length=80)],
    chave: Annotated[str, Field(min_length=2, max_length=10)],
    config: RunnableConfig,
    modelo: Template = "scrum",
    descricao: Annotated[str, Field(max_length=500)] = "",
    chave_escolhida_pelo_usuario: bool = False,
) -> str:
    """Propõe criar um projeto no Jira; o usuário confirma no cartão antes de qualquer criação.
    Use SÓ quando o usuário pedir para criar um projeto. `chave`: 2 a 10 letras maiúsculas ou
    dígitos, começando por letra, derivada do nome (ex.: "Loja Online" → "LOJA"). `modelo`:
    "scrum" (padrão), "kanban" ou "negocio" (tarefas de áreas de negócio).
    `chave_escolhida_pelo_usuario`: true só se o usuário disse a chave; se for false e ela estiver
    em uso, a proposta sai com a chave livre que o Jira sugerir."""
    ctx = tool_context(config)
    if ctx.jira is None:
        return "O Jira não está conectado: peça para o usuário conectar em Settings."
    key, name = chave.strip().upper(), " ".join(nome.split())
    if not KEY.match(key):
        return (
            f'A chave "{key}" não serve: use de 2 a 10 letras maiúsculas ou dígitos, começando '
            "por letra. Proponha de novo com outra chave."
        )
    if len(name) < 2:
        return "Informe o nome do projeto."
    try:
        check = await ctx.jira.check_project_key(key)
    except JiraToolError as exc:
        return f"Não foi possível conferir a chave no Jira: {exc}"
    replaced = key
    if check.problem and not chave_escolhida_pelo_usuario and check.suggestion:
        # F22-RF-02: a chave foi do agente; o cartão mostra a sugerida e o usuário confirma.
        replaced, key = key, check.suggestion
        if not KEY.match(key) or (await ctx.jira.check_project_key(key)).problem:
            return (
                f'A chave "{replaced}" está em uso e a sugestão do Jira não serve. Escolha outra.'
            )
    elif check.problem:
        hint = f' Chave livre sugerida pelo Jira: "{check.suggestion}".' if check.suggestion else ""
        return (
            f'A chave "{key}" não pode ser usada: {check.problem}.{hint} Nenhum cartão foi '
            "criado: diga ao usuário que a chave que ele pediu está em uso e pergunte se pode "
            "usar a sugerida."
        )
    type_key, template_key, label = TEMPLATES[modelo]
    payload = {
        "key": key,
        "name": name,
        "projectTypeKey": type_key,
        "projectTemplateKey": template_key,
        "description": descricao.strip(),
        "assigneeType": "UNASSIGNED",
    }
    preview = {
        "project_key": key,
        "name": name,
        "template": modelo,
        "template_label": label,
        "description": descricao.strip(),
        "lead": ctx.jira.account_name,
    }
    action = await ctx.actions.propose("create_project", payload, {}, [], preview)
    ctx.proposed.append(action)
    swapped = (
        f' A chave "{replaced}" está em uso; o cartão usa "{key}", sugerida pelo Jira: avise o '
        "usuário."
        if key != replaced
        else ""
    )
    return (
        f'Proposta de criar o projeto {key} ("{name}", {label}) pronta no cartão '
        f"(ação {action.id}). Nada foi criado: o usuário confirma ou recusa no cartão.{swapped}"
    )


PROJECT_TOOLS: list[BaseTool] = [propor_criacao_projeto]
