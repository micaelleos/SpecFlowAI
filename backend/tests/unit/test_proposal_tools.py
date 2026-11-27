"""O agente lê e revisa a proposta editada (F14-RF-04, F14-RF-05): mesma ação, sem cartão novo."""

from typing import Any, cast

import pytest
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from app.agent.fake_llm import ScriptedChatModel
from app.agent.spec.schema import WorkItemSpec
from app.core.config import Settings
from app.services.action_edits import ActionEditService
from app.services.chat import ChatService
from app.services.jira_connections import JiraConnectionService
from tests.chat_fakes import NOW, FakeJiraService, MemoryChatStore, call, jira_handler
from tests.spec_fixtures import pix_story_data

UID = "uid-alice"


class Turns:
    def __init__(self) -> None:
        self.store = MemoryChatStore()
        self.llm = ScriptedChatModel(responses=[])
        self.chat = ChatService(
            self.store,
            cast(JiraConnectionService, FakeJiraService(handler=jira_handler())),
            self.llm,
            Settings(env="test"),
            clock=lambda: NOW,
        )
        self.conversation = "new"

    async def turn(self, text: str, *responses: AIMessage) -> None:
        self.llm.responses += list(responses)
        cid, events = await self.chat.open_turn(UID, self.conversation, text)
        _ = [e async for e in events]
        self.conversation = cid

    def actions(self) -> list[dict[str, Any]]:
        return self.store.list_actions(UID, self.conversation)


async def _proposed_and_edited() -> tuple[Turns, str]:
    turns = Turns()
    await turns.turn(
        "Crie a story do Pix",
        call("propor_criacao_issue", {"project_key": "ABC", "spec": pix_story_data()}),
        AIMessage("Confirme no cartão."),
    )
    [doc] = turns.actions()
    edits = ActionEditService(turns.store, clock=lambda: NOW)
    edited = WorkItemSpec.model_validate(pix_story_data(title="Login com SSO"))
    await edits.save(UID, doc["id"], edited, None, doc["payloadHash"])
    return turns, doc["id"]


def _tool_result(llm: ScriptedChatModel, name: str) -> str:
    for messages in reversed(llm.calls):
        for m in messages:
            if isinstance(m, ToolMessage) and m.name == name:
                return str(m.content)
    raise AssertionError(name)


@pytest.mark.req("F14-RF-05")
async def test_agente_ve_o_titulo_editado_e_le_a_proposta() -> None:
    turns, aid = await _proposed_and_edited()

    await turns.turn(
        "Qual o título atual?",
        call("ler_proposta", {"action_id": aid}),
        AIMessage("O título é Login com SSO."),
    )

    system = str(next(m for m in turns.llm.calls[-2] if isinstance(m, SystemMessage)).content)
    assert '"Login com SSO"' in system
    assert "(editada pelo usuário)" in system
    read = _tool_result(turns.llm, "ler_proposta")
    assert '"title": "Login com SSO"' in read
    assert "mantenha as mudanças dele" in read


@pytest.mark.req("F14-RF-04")
async def test_revisar_regrava_a_mesma_acao() -> None:
    turns, aid = await _proposed_and_edited()
    revised = pix_story_data(title="Login com SSO")
    revised["acceptance_criteria"].append(
        {
            "id": "CA-03",
            "kind": "erro",
            "title": "Senha expirada",
            "given": ["minha senha expirou"],
            "when": ["tento entrar"],
            "then": ["vejo o pedido para trocar a senha"],
        }
    )

    await turns.turn(
        f'Refine the section "Critérios de aceite" of proposal {aid}: adicione senha expirada',
        call("ler_proposta", {"action_id": aid}),
        call("revisar_proposta", {"action_id": aid, "spec": revised}, "call-2"),
        AIMessage("Acrescentei o cenário no mesmo cartão."),
    )

    [doc] = turns.actions()  # nenhum cartão novo
    assert doc["id"] == aid
    assert doc["editedBy"] == "agent"
    assert doc["version"] == 3
    assert doc["payload"]["spec"]["title"] == "Login com SSO"
    assert doc["payload"]["spec"]["acceptance_criteria"][-1]["title"] == "Senha expirada"
    assert doc["agentVersion"]["payloadHash"] == doc["payloadHash"]  # "Restore" volta aqui
    assert "revisada no mesmo cartão" in _tool_result(turns.llm, "revisar_proposta")


@pytest.mark.req("F14-RF-04")
async def test_revisar_recusa_proposta_de_outra_conversa_ou_tratada() -> None:
    turns, aid = await _proposed_and_edited()
    other = Turns()
    other.store, other.chat, other.llm = turns.store, turns.chat, turns.llm
    await other.turn(
        "Revise",
        call("revisar_proposta", {"action_id": aid, "spec": pix_story_data()}),
        AIMessage("Não consegui."),
    )
    assert "não existe nesta conversa" in _tool_result(turns.llm, "revisar_proposta")

    doc = turns.store._action(UID, aid)
    assert doc is not None
    doc["status"] = "rejected"
    await turns.turn(
        "Revise",
        call("revisar_proposta", {"action_id": aid, "spec": pix_story_data()}),
        AIMessage("Já foi recusada."),
    )
    assert "não foi revisada" in _tool_result(turns.llm, "revisar_proposta")
    assert (turns.store.get_action(UID, aid) or {})["payload"]["spec"]["title"] == "Login com SSO"
