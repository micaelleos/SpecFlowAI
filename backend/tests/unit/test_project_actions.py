"""Criar o projeto depois do Confirm (F22-RF-01, F22-RF-03, F22-RF-04, F22-RT-01, F22-RT-04)."""

import json
import logging
from typing import Any, cast

import httpx
import pytest
from langchain_core.messages import AIMessage

from app.agent.fake_llm import ScriptedChatModel
from app.core.config import Settings
from app.services.actions import ActionFailedError, ActionService
from app.services.chat import ChatService
from app.services.conversations import ConversationService
from app.services.jira_connections import JiraConnectionService
from tests.chat_fakes import NOW, SITE, FakeJiraService, MemoryChatStore, call

ARGS = {"nome": "Loja Online", "chave": "LOJA", "modelo": "scrum"}


class Jira:
    def __init__(self, status: int = 201) -> None:
        self.status = status
        self.created: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/rest/api/3/projectvalidate/key":
            return httpx.Response(200, json={"errorMessages": [], "errors": {}})
        if path == "/rest/api/3/myself":
            return httpx.Response(200, json={"accountId": "acc-po", "displayName": "PO"})
        if path == "/rest/api/3/project" and request.method == "POST":
            self.created.append(json.loads(request.content))
            if self.status != 201:
                return httpx.Response(self.status, json={"errorMessages": ["You cannot"]})
            return httpx.Response(201, json={"id": 10001, "key": "LOJA"})
        if path == "/rest/api/3/project/search":
            return httpx.Response(200, json={"values": []})
        raise AssertionError(f"inesperado: {request.method} {path}")


class Cache:
    def __init__(self) -> None:
        self.cleared: list[str] = []

    def clear_projects(self, uid: str) -> None:
        self.cleared.append(uid)


async def _propose(
    jira: Jira, project: str | None = None
) -> tuple[MemoryChatStore, FakeJiraService, str, str]:
    store = MemoryChatStore()
    fake = FakeJiraService(handler=jira)
    llm = ScriptedChatModel(
        responses=[call("propor_criacao_projeto", ARGS), AIMessage("Confirme no cartão.")]
    )
    chat = ChatService(
        store, cast(JiraConnectionService, fake), llm, Settings(env="test"), clock=lambda: NOW
    )
    conv = await ConversationService(store, clock=lambda: NOW).create("uid-alice", None, project)
    _, events = await chat.open_turn("uid-alice", conv.id, "Crie o projeto Loja Online")
    [e async for e in events]
    [action] = store.list_actions("uid-alice", conv.id)
    assert jira.created == []  # nada criado antes do Confirm
    return store, fake, conv.id, str(action["id"])


def _service(store: MemoryChatStore, fake: FakeJiraService, cache: Cache) -> ActionService:
    return ActionService(
        store,
        cast(JiraConnectionService, fake),
        Settings(env="test"),
        clock=lambda: NOW,
        projects_cache=cache,
    )


@pytest.mark.req("F22-RF-01")
@pytest.mark.req("F22-RF-03")
@pytest.mark.req("F22-RT-01")
@pytest.mark.req("F22-RT-04")
async def test_confirmar_cria_fixa_e_descarta_o_cache(caplog: pytest.LogCaptureFixture) -> None:
    jira, cache = Jira(), Cache()
    store, fake, cid, aid = await _propose(jira)
    doc = store.get_action("uid-alice", aid)
    assert doc is not None

    with caplog.at_level(logging.INFO, logger="app.actions"):
        out = await _service(store, fake, cache).confirm(
            "uid-alice", aid, payload_hash=doc["payloadHash"]
        )

    assert out.status == "done"
    assert out.result is not None
    assert out.result.model_dump() == {"issue_key": "LOJA", "url": f"{SITE}/browse/LOJA"}
    [body] = jira.created
    assert body == {**doc["payload"], "leadAccountId": "acc-po"}
    assert store.conversations["uid-alice"][cid]["projectKey"] == "LOJA"
    assert cache.cleared == ["uid-alice"]
    [message] = [m for m in store.messages[("uid-alice", cid)] if m.get("actionId") == aid]
    assert "criou o projeto LOJA" in message["content"]
    assert "A conversa agora é do projeto LOJA" in message["content"]
    [audit] = [r for r in caplog.records if r.getMessage() == "jira_write"]
    fields = cast(dict[str, Any], audit.__dict__["fields"])
    assert (fields["kind"], fields["issue_key"], fields["result"]) == (
        "create_project",
        "LOJA",
        "done",
    )


@pytest.mark.req("F22-RF-03")
async def test_conversa_com_projeto_nao_muda() -> None:
    jira, cache = Jira(), Cache()
    store, fake, cid, aid = await _propose(jira, project="ABC")
    await _service(store, fake, cache).confirm("uid-alice", aid)
    assert store.conversations["uid-alice"][cid]["projectKey"] == "ABC"


@pytest.mark.req("F22-RF-04")
async def test_sem_permissao_nada_criado_e_mensagem_clara() -> None:
    jira, cache = Jira(status=403), Cache()
    store, fake, cid, aid = await _propose(jira)

    with pytest.raises(ActionFailedError) as failed:
        await _service(store, fake, cache).confirm("uid-alice", aid)

    assert failed.value.code == "jira-project-forbidden"
    assert "administrador do Jira" in (failed.value.detail or "")
    assert store.conversations["uid-alice"][cid].get("projectKey") is None
    assert cache.cleared == []


@pytest.mark.req("F22-RT-01")
async def test_payload_alterado_nao_executa() -> None:
    jira, cache = Jira(), Cache()
    store, fake, _, aid = await _propose(jira)
    for doc in store.actions["uid-alice"]:
        if doc["id"] == aid:
            doc["payload"]["key"] = "OUTRO"

    with pytest.raises(ActionFailedError) as failed:
        await _service(store, fake, cache).confirm("uid-alice", aid)
    assert failed.value.code == "action-integrity"
    assert jira.created == []
