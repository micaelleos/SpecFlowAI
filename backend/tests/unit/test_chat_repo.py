"""O chat com o repositório vinculado (F17-RF-02, F17-RF-05, F17-RT-05)."""

import logging
from typing import Any, cast

import httpx
import pytest
from langchain_core.messages import AIMessage, SystemMessage

from app.agent.fake_llm import ScriptedChatModel
from app.core.config import Settings
from app.integrations.github.client import GitHubClient
from app.services.chat import REPO_UNAVAILABLE_NOTE, ChatService
from app.services.conversations import ConversationService
from app.services.jira_connections import JiraConnectionService
from tests.chat_fakes import NOW, FakeJiraService, MemoryChatStore, call, jira_handler
from tests.github_fake import VALID, FakeGitHub

LINK = {"fullName": "po/loja", "url": "https://github.com/po/loja", "defaultBranch": "main"}


class FakeRepoLinks:
    def __init__(self, token: str = VALID, linked: bool = True) -> None:
        self.github = FakeGitHub()
        self.token = token
        self.has_link = linked
        self.invalid: list[dict[str, Any]] = []

    async def linked(
        self, uid: str, project_key: str
    ) -> tuple[GitHubClient, dict[str, Any], dict[str, Any]] | None:
        if not self.has_link or project_key != "ABC":
            return None
        client = GitHubClient(self.token, transport=httpx.MockTransport(self.github))
        return client, {"id": "gh-1"}, LINK

    async def mark_invalid(self, uid: str, current: dict[str, Any]) -> None:
        self.invalid.append(current)


async def _turn(
    llm: ScriptedChatModel, links: FakeRepoLinks, project: str | None = "ABC"
) -> list[Any]:
    store = MemoryChatStore()
    service = ChatService(
        store,
        cast(JiraConnectionService, FakeJiraService(handler=jira_handler())),
        llm,
        Settings(env="test"),
        clock=lambda: NOW,
        github=links,
    )
    conv = await ConversationService(store, clock=lambda: NOW).create("uid-alice", None, project)
    _, events = await service.open_turn("uid-alice", conv.id, "Valide o CPF no cadastro")
    return [e async for e in events]


def _system(llm: ScriptedChatModel, i: int = 0) -> str:
    return str(next(m for m in llm.calls[i] if isinstance(m, SystemMessage)).content)


@pytest.mark.req("F17-RF-02")
@pytest.mark.req("F17-RT-05")
async def test_projeto_com_repositorio_recebe_nota_e_ferramentas(
    caplog: pytest.LogCaptureFixture,
) -> None:
    llm = ScriptedChatModel(
        responses=[
            call("ler_arquivo_do_repositorio", {"caminho": "src/cadastro/cpf.py"}),
            AIMessage("Achei o módulo."),
        ]
    )
    with caplog.at_level(logging.INFO, logger="app.github"):
        await _turn(llm, FakeRepoLinks())

    system = _system(llm)
    assert "## Repositório do código do projeto" in system
    assert "make test" in system
    assert "buscar_no_repositorio" in llm.bound_tools
    assert "ler_arquivo_do_repositorio" in llm.bound_tools
    [read] = [r for r in caplog.records if r.getMessage() == "repo_read"]
    fields = cast(dict[str, Any], read.__dict__["fields"])
    assert fields["files"] == 2  # o AGENTS.md da nota e o arquivo lido pelo agente
    assert "cpf" not in str(fields)  # nem caminho nem conteúdo no log


@pytest.mark.req("F17-RF-04")
@pytest.mark.req("F17-RT-05")
async def test_sem_vinculo_ou_sem_projeto_nao_le_o_repositorio() -> None:
    for links, project in ((FakeRepoLinks(linked=False), "ABC"), (FakeRepoLinks(), None)):
        llm = ScriptedChatModel(responses=[AIMessage("ok")])
        await _turn(llm, links, project)
        assert "Repositório do código" not in _system(llm)
        assert "buscar_no_repositorio" not in llm.bound_tools
        assert links.github.requests == []


@pytest.mark.req("F17-RF-05")
async def test_token_recusado_segue_sem_o_codigo() -> None:
    links = FakeRepoLinks(token="github_pat_revogado_0000000000000")
    llm = ScriptedChatModel(responses=[AIMessage("ok")])
    await _turn(llm, links)

    assert REPO_UNAVAILABLE_NOTE in _system(llm)
    assert "buscar_no_repositorio" not in llm.bound_tools
    assert links.invalid == [{"id": "gh-1"}]
