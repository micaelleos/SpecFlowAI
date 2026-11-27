"""O agente fixa o projeto da conversa (F21-RF-01..03, F21-RT-01..04)."""

import logging
from typing import Any, cast

import pytest
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from app.agent.fake_llm import ScriptedChatModel
from app.agent.tools.confluence_write_tools import WRITE_NOTE
from app.agent.tools.context import Project, ToolContext
from app.agent.tools.conversation_tools import NOT_AVAILABLE, PIN_TOOL, fixar_projeto_da_conversa
from app.core.config import Settings
from app.services.chat import NO_PROJECT_NOTE, ChatService
from app.services.chat_events import ToolStartEvent
from app.services.conversations import ConversationService
from app.services.jira_connections import JiraConnectionService
from tests.chat_fakes import (
    NOW,
    FakeJiraReader,
    FakeJiraService,
    MemoryChatStore,
    call,
    jira_handler,
)
from tests.confluence_fake import FakeConfluenceReader
from tests.unit.test_chat_confluence import FakeLinks

PROJECTS = [{"key": "SCRUM", "name": "Minha equipe"}, {"key": "ABC", "name": "Loja"}]


class _Pinner:
    def __init__(self, current: str | None = None) -> None:
        self.current = current
        self.calls: list[str] = []

    async def pin(self, project_key: str) -> str | None:
        self.calls.append(project_key)
        self.current = self.current or project_key
        return self.current


def _ctx(pinner: _Pinner | None) -> ToolContext:
    jira = FakeJiraReader([Project("SCRUM", "Minha equipe")])
    return ToolContext(
        uid="u", conversation_id="c", jira=jira, actions=cast(Any, None), pinner=pinner
    )


async def _pin(ctx: ToolContext, key: str) -> str:
    result = await fixar_projeto_da_conversa.ainvoke(
        {"chave_do_projeto": key}, config={"configurable": {"ctx": ctx}}
    )
    return str(result)


@pytest.mark.req("F21-RF-01")
async def test_ferramenta_fixa_projeto_que_a_conta_ve() -> None:
    pinner = _Pinner()
    ctx = _ctx(pinner)
    assert "fixada no projeto SCRUM" in await _pin(ctx, "scrum")
    assert ctx.pinned == "SCRUM"
    assert pinner.calls == ["SCRUM"]


@pytest.mark.req("F21-RF-01")
async def test_projeto_desconhecido_nao_fixa_e_lista_os_disponiveis() -> None:
    pinner = _Pinner()
    ctx = _ctx(pinner)
    result = await _pin(ctx, "XYZ")
    assert "Nada foi fixado" in result
    assert "SCRUM (Minha equipe)" in result
    assert ctx.pinned is None
    assert pinner.calls == []


@pytest.mark.req("F21-RF-03")
@pytest.mark.req("F21-RT-03")
async def test_nao_troca_nem_fixa_duas_vezes() -> None:
    assert await _pin(_ctx(None), "SCRUM") == NOT_AVAILABLE  # conversa com projeto: sem pinner
    ctx = _ctx(_Pinner())
    await _pin(ctx, "SCRUM")
    assert await _pin(ctx, "SCRUM") == NOT_AVAILABLE  # uma fixação por turno
    raced = _ctx(_Pinner(current="ABC"))  # outra aba fixou antes (F21-RT-01)
    assert "já estava fixada no projeto ABC" in await _pin(raced, "SCRUM")
    assert raced.pinned is None


async def _turn(
    llm: ScriptedChatModel, *, project: str | None, links: FakeLinks | None = None
) -> tuple[MemoryChatStore, str, list[Any]]:
    store = MemoryChatStore()
    service = ChatService(
        store,
        cast(JiraConnectionService, FakeJiraService(handler=jira_handler(PROJECTS))),
        llm,
        Settings(env="test", confluence_enabled=True, confluence_write_enabled=True),
        clock=lambda: NOW,
        confluence=links or FakeLinks(FakeConfluenceReader()),
    )
    conv = await ConversationService(store, clock=lambda: NOW).create("uid-alice", None, project)
    _, events = await service.open_turn("uid-alice", conv.id, "No SCRUM, leia o glossário")
    return store, conv.id, [e async for e in events]


def _system(messages: list[Any]) -> str:
    return str(next(m for m in messages if isinstance(m, SystemMessage)).content)


@pytest.mark.req("F21-RF-02")
@pytest.mark.req("F21-RT-03")
@pytest.mark.req("F21-RT-04")
async def test_fixa_e_segue_o_mesmo_turno_com_a_documentacao(
    caplog: pytest.LogCaptureFixture,
) -> None:
    llm = ScriptedChatModel(
        responses=[
            call(PIN_TOOL, {"chave_do_projeto": "SCRUM"}),
            call("ler_pagina_confluence", {"page_id": "101"}, "call-2"),
            AIMessage("Li a RN-03 do SCRUM."),
        ]
    )
    with caplog.at_level(logging.INFO, logger="app.chat"):
        store, conv_id, events = await _turn(llm, project=None)

    assert store.conversations["uid-alice"][conv_id]["projectKey"] == "SCRUM"
    first, second = _system(llm.calls[0]), _system(llm.calls[1])
    assert NO_PROJECT_NOTE in first
    assert "## Documentação do projeto no Confluence" not in first
    assert "## Documentação do projeto no Confluence" in second
    assert WRITE_NOTE in second
    assert NO_PROJECT_NOTE not in second
    # A continuação parte da chamada e da resposta da ferramenta de fixar.
    pin_reply = [m for m in llm.calls[1] if isinstance(m, ToolMessage)]
    assert [m.name for m in pin_reply] == [PIN_TOOL]
    read = [m for m in llm.calls[2] if isinstance(m, ToolMessage) and m.name != PIN_TOOL]
    assert "RN-03" in str(read[0].content)
    assert [e.name for e in events if isinstance(e, ToolStartEvent)] == [
        PIN_TOOL,
        "ler_pagina_confluence",
    ]
    assert PIN_TOOL not in llm.bound_tools  # a 2ª passada não oferece a ferramenta
    pinned = [r for r in caplog.records if r.getMessage() == "conversation_pinned"]
    assert len(pinned) == 1
    fields = cast(dict[str, Any], pinned[0].__dict__["fields"])
    assert fields["project_key"] == "SCRUM"
    assert "uid-alice" not in str(fields)


@pytest.mark.req("F21-RF-03")
async def test_conversa_com_projeto_nao_recebe_a_ferramenta() -> None:
    llm = ScriptedChatModel(responses=[AIMessage("ok")])
    await _turn(llm, project="SCRUM")
    assert PIN_TOOL not in llm.bound_tools


@pytest.mark.req("F21-RF-01")
async def test_conversa_sem_projeto_recebe_a_ferramenta() -> None:
    llm = ScriptedChatModel(responses=[AIMessage("ok")])
    store, conv_id, _ = await _turn(llm, project=None)
    assert PIN_TOOL in llm.bound_tools
    assert store.conversations["uid-alice"][conv_id]["projectKey"] is None
