"""O agente propõe exportar o épico por PR (F18-RF-01, F18-RF-05, F18-RT-01)."""

from typing import Any, cast

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.agent.fake_llm import ScriptedChatModel
from app.core.config import Settings
from app.services.chat import TOOLSETS, ChatService
from app.services.conversations import ConversationService
from app.services.jira_connections import JiraConnectionService
from tests.chat_fakes import NOW, FakeJiraService, MemoryChatStore, call, jira_handler
from tests.export_fakes import UID, GitHubLinks, seed_epic


async def _turn(
    links: GitHubLinks, key: str = "ABC-10", seed: bool = True
) -> tuple[MemoryChatStore, ScriptedChatModel, list[Any]]:
    store = MemoryChatStore()
    if seed:
        seed_epic(store)
    llm = ScriptedChatModel(
        responses=[
            call("propor_exportacao_para_repositorio", {"chave_do_epico": key}),
            AIMessage("Confira o cartão."),
        ]
    )
    chat = ChatService(
        store,
        cast(JiraConnectionService, FakeJiraService(handler=jira_handler())),
        llm,
        Settings(env="test"),
        clock=lambda: NOW,
        github=links,
    )
    conv = await ConversationService(store, clock=lambda: NOW).create(UID, None, "ABC")
    _, events = await chat.open_turn(UID, conv.id, "Exporte o épico ABC-10 para o repositório")
    return store, llm, [e async for e in events]


def _tool_text(llm: ScriptedChatModel) -> str:
    return str(next(m for m in llm.calls[-1] if isinstance(m, ToolMessage)).content)


@pytest.mark.req("F18-RF-01")
@pytest.mark.req("F18-RT-01")
async def test_propoe_o_pr_sem_escrever() -> None:
    links = GitHubLinks()
    store, llm, _ = await _turn(links)
    [action] = [a for a in store.actions[UID] if a.get("kind") == "create_pull_request"]
    assert action["status"] == "pending"
    assert action["payloadHash"]
    assert action["preview"]["branch"] == "specflow/abc-10"
    assert "Nada foi escrito" in _tool_text(llm)
    assert links.github.branches == set()
    assert links.github.pulls == []


@pytest.mark.req("F18-RF-05")
async def test_sem_repositorio_nao_ha_ferramenta() -> None:
    assert all(
        ("propor_exportacao_para_repositorio" in [t.name for t in tools]) == name.endswith("_repo")
        for name, tools in TOOLSETS.items()
    )
    links = GitHubLinks(linked=False)
    store = MemoryChatStore()
    llm = ScriptedChatModel(responses=[AIMessage("Vincule um repositório.")])
    chat = ChatService(
        store,
        cast(JiraConnectionService, FakeJiraService(handler=jira_handler())),
        llm,
        Settings(env="test"),
        clock=lambda: NOW,
        github=links,
    )
    conv = await ConversationService(store, clock=lambda: NOW).create(UID, None, "ABC")
    _, events = await chat.open_turn(UID, conv.id, "Exporte o épico ABC-10")
    [e async for e in events]
    assert "propor_exportacao_para_repositorio" not in llm.bound_tools


@pytest.mark.req("F18-RF-05")
async def test_epico_fora_do_historico_nao_propoe() -> None:
    store, llm, _ = await _turn(GitHubLinks(), key="ABC-77")
    assert not [a for a in store.actions[UID] if a.get("kind") == "create_pull_request"]
    assert "não é um épico criado pelo SpecFlow" in _tool_text(llm)


@pytest.mark.req("F18-RF-05")
def test_prompt_diz_para_vincular_sem_repositorio() -> None:
    from datetime import date

    from app.agent.graph import system_prompt

    for version in ("v1", "v2"):
        text = system_prompt(version, today=date(2026, 11, 27), jira_connected=True)
        assert "propor_exportacao_para_repositorio" in text
        assert "vincular um repositório em Projects" in text
