"""A ferramenta `propor_criacao_projeto` (F22-RF-01, F22-RF-02, F22-RT-02): valida e só propõe."""

from datetime import date
from typing import Any

import pytest
from langchain_core.runnables import RunnableConfig

from app.agent.graph import system_prompt
from app.agent.tools.context import JiraToolError, ToolContext
from app.agent.tools.project_tools import TEMPLATES, propor_criacao_projeto
from app.services.chat import TOOLSETS
from tests.chat_fakes import FakeJiraReader, MemorySink


def _ctx() -> tuple[ToolContext, FakeJiraReader, MemorySink]:
    reader, sink = FakeJiraReader(), MemorySink()
    return ToolContext("u", "c", reader, sink), reader, sink


async def _call(ctx: ToolContext, **args: Any) -> str:
    config: RunnableConfig = {"configurable": {"ctx": ctx}}
    return str(await propor_criacao_projeto.ainvoke(args, config=config))


@pytest.mark.req("F22-RF-01")
@pytest.mark.req("F22-RT-02")
async def test_propoe_com_modelo_e_responsavel() -> None:
    ctx, _, sink = _ctx()
    out = await _call(
        ctx, nome="  Loja   Online ", chave="lojaon", modelo="kanban", descricao="E-commerce"
    )

    assert "Nada foi criado" in out
    [action] = sink.actions
    assert action["kind"] == "create_project"
    assert action["payload"] == {
        "key": "LOJAON",
        "name": "Loja Online",
        "projectTypeKey": "software",
        "projectTemplateKey": TEMPLATES["kanban"][1],
        "description": "E-commerce",
        "assigneeType": "UNASSIGNED",
    }
    assert action["preview"]["lead"] == "Pessoa PO"
    assert action["preview"]["template_label"] == "Kanban"
    assert len(ctx.proposed) == 1
    assert all(
        tools[-1] is propor_criacao_projeto
        for name, tools in TOOLSETS.items()
        if not name.endswith("_repo")
    )


@pytest.mark.req("F22-RF-02")
async def test_chave_em_uso_ou_invalida_nao_vira_cartao() -> None:
    ctx, reader, sink = _ctx()
    used = await _call(ctx, nome="Loja", chave="ABC", chave_escolhida_pelo_usuario=True)
    assert 'Chave livre sugerida pelo Jira: "ABC2"' in used
    bad = await _call(ctx, nome="Loja", chave="1AB")
    assert "não serve" in bad
    reader.fail = JiraToolError("o Jira não respondeu")
    assert "Não foi possível conferir" in await _call(ctx, nome="Loja", chave="NOVA")
    assert sink.actions == []
    assert ctx.proposed == []


@pytest.mark.req("F22-RF-05")
async def test_sem_jira_e_prompt_so_quando_pedido() -> None:
    ctx = ToolContext("u", "c", None, MemorySink())
    assert "não está conectado" in await _call(ctx, nome="Loja", chave="LOJA")
    for version in ("v1", "v2"):
        assert "propor_criacao_projeto" in system_prompt(
            version, today=date(2026, 11, 27), jira_connected=True
        )
        assert "só quando o usuário pedir" in system_prompt(
            version, today=date(2026, 11, 27), jira_connected=True
        )


@pytest.mark.req("F22-RF-02")
async def test_chave_do_agente_em_uso_sai_com_a_sugerida() -> None:
    ctx, _, sink = _ctx()
    out = await _call(ctx, nome="Loja Nova", chave="ABC")
    [action] = sink.actions
    assert action["payload"]["key"] == "ABC2"
    assert '"ABC" está em uso; o cartão usa "ABC2"' in out
