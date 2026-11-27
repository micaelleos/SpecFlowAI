"""Exportar as specs de um épico para o repositório, por PR (F18, ADR-011).

A ferramenta só prepara a ação proposta: o PR é aberto depois do Confirm, com os arquivos exibidos
no cartão (F18-RT-01).
"""

from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from pydantic import Field

from app.agent.tools.context import SpecExportError, tool_context

NO_REPO = (
    "Este projeto não tem repositório vinculado: peça para o usuário vincular um em Projects, "
    '"Code repository" (e conectar o GitHub em Settings). Nada foi proposto.'
)
PROGRESS = {"propor_exportacao_para_repositorio": "Preparando o PR com as specs…"}


@tool
async def propor_exportacao_para_repositorio(
    chave_do_epico: Annotated[
        str, Field(min_length=3, max_length=20, pattern=r"^[A-Za-z][A-Za-z0-9_]*-\d+$")
    ],
    config: RunnableConfig,
) -> str:
    """Propõe abrir um PR no repositório vinculado com as specs (formato Spec Kit) de um épico
    criado pelo SpecFlow e das histórias dele. Use SÓ quando o usuário pedir para exportar ou
    levar as specs para o repositório. O conteúdo sai das specs já criadas, sem mudanças."""
    ctx = tool_context(config)
    if ctx.spec_exporter is None:
        return NO_REPO
    try:
        draft = await ctx.spec_exporter.draft(chave_do_epico)
    except SpecExportError as exc:
        return f"Não dá para exportar: {exc} Nada foi proposto."
    action = await ctx.actions.propose(draft.kind, draft.payload, {}, [], draft.preview)
    ctx.proposed.append(action)
    files = ", ".join(f["path"] for f in draft.payload["files"])
    return (
        f"Proposta de PR pronta no cartão (ação {action.id}): branch {draft.payload['branch']} em "
        f"{draft.payload['repo']}, com {files}. Nada foi escrito: o usuário confirma ou recusa."
    )


EXPORT_TOOLS: list[BaseTool] = [propor_exportacao_para_repositorio]
