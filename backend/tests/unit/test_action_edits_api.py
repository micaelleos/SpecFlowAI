"""Editar a proposta antes de confirmar (F14): prévia sem gravar, versão nova, restaurar, hash."""

import json
import logging
from collections.abc import Iterator
from datetime import timedelta
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from app.agent.fake_llm import ScriptedChatModel
from app.api.deps import (
    get_action_edit_service,
    get_action_service,
    get_chat_service,
    get_verifier,
)
from app.core.config import Settings, get_settings
from app.main import create_app
from app.services.action_edits import ActionEditService
from app.services.actions import ActionService
from app.services.chat import ChatService
from app.services.jira_connections import JiraConnectionService
from tests.chat_fakes import NOW, FakeJiraService, MemoryChatStore
from tests.fakes import FakeVerifier
from tests.spec_fixtures import pix_story_data
from tests.unit.test_actions_api import ALICE, BOB, App, Jira

AGENT_TITLE = "Permitir pagamento com Pix no checkout da loja"


@pytest.fixture
def app() -> Iterator[App]:
    jira = Jira()
    store = MemoryChatStore()
    fake_jira = cast(JiraConnectionService, FakeJiraService(handler=jira))
    llm = ScriptedChatModel(responses=[])
    settings = Settings(env="test")
    api = create_app()
    api.dependency_overrides[get_settings] = lambda: settings
    api.dependency_overrides[get_verifier] = FakeVerifier
    api.dependency_overrides[get_chat_service] = lambda: ChatService(
        store, fake_jira, llm, settings, clock=lambda: NOW
    )
    api.dependency_overrides[get_action_service] = lambda: ActionService(
        store, fake_jira, settings, clock=lambda: NOW
    )
    api.dependency_overrides[get_action_edit_service] = lambda: ActionEditService(
        store, clock=lambda: NOW
    )
    with TestClient(api) as client:
        yield App(client, store, jira, llm)


def _card(app: App, aid: str) -> dict[str, Any]:
    doc = app.store.get_action("uid-alice", aid)
    assert doc is not None
    [card] = [
        c
        for c in app.client.get(
            f"/api/v1/conversations/{doc['conversationId']}/actions", headers=ALICE
        ).json()
        if c["id"] == aid
    ]
    return cast(dict[str, Any], card)


def _edited(**overrides: Any) -> dict[str, Any]:
    spec = pix_story_data(title="Login com SSO", **overrides)
    spec["acceptance_criteria"].append(
        {
            "id": "CA-09",  # a API renumera (F14-RT-04)
            "kind": "borda",
            "title": "Sessão expirada",
            "given": ["minha sessão expirou"],
            "when": ["abro o checkout"],
            "then": ["vejo a tela de login"],
        }
    )
    return spec


def _save(app: App, aid: str, spec: dict[str, Any], base: str, **extra: Any) -> Any:
    body = {"spec": spec, "base_hash": base, **extra}
    return app.client.put(f"/api/v1/actions/{aid}/spec", json=body, headers=ALICE)


@pytest.mark.req("F14-RF-01")
@pytest.mark.req("F14-RF-06")
@pytest.mark.req("F14-RT-03")
def test_previa_recalcula_sem_gravar(app: App) -> None:
    _, aid = app.propose()
    card = _card(app, aid)
    assert card["spec"]["title"] == AGENT_TITLE
    assert (card["version"], card["edited_by"]) == (1, "agent")

    spec = pix_story_data(objective="", acceptance_criteria=[])
    response = app.client.post(f"/api/v1/actions/{aid}/preview", json={"spec": spec}, headers=ALICE)

    assert response.status_code == 200
    body = response.json()
    assert body["readiness"]["ready"] is False  # seção obrigatória vazia derruba a prontidão
    assert "agent-ready" not in body["labels"]
    assert body["preview"]["sections"][0]["title"] == "Objetivo"
    assert _card(app, aid)["payload_hash"] == card["payload_hash"]  # nada gravado


@pytest.mark.req("F14-RF-02")
@pytest.mark.req("F14-RT-01")
@pytest.mark.req("F14-RT-04")
@pytest.mark.req("F14-RT-05")
def test_salvar_e_confirmar_cria_o_conteudo_editado(
    app: App, caplog: pytest.LogCaptureFixture
) -> None:
    _, aid = app.propose()
    base = _card(app, aid)["payload_hash"]

    with caplog.at_level(logging.INFO, logger="app.actions"):
        saved = _save(app, aid, _edited(), base, priority="High")

    assert saved.status_code == 200
    out = saved.json()
    assert (out["version"], out["edited_by"]) == (2, "user")
    assert out["payload_hash"] != base
    assert out["preview"]["summary"] == "Login com SSO"
    assert out["preview"]["priority"] == "High"
    assert [c["id"] for c in out["spec"]["acceptance_criteria"]] == ["CA-01", "CA-02", "CA-03"]
    assert out["preview"]["project_key"] == "ABC"  # o resto da proposta fica
    [edited] = [r for r in caplog.records if r.getMessage() == "action_edited"]
    fields = cast(dict[str, Any], edited.__dict__["fields"])
    assert (fields["version"], fields["by"]) == (2, "user")
    assert "alice" not in json.dumps(fields)

    stale = app.client.post(
        f"/api/v1/actions/{aid}/confirm", json={"payload_hash": base}, headers=ALICE
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "action-changed"
    assert stale.json()["action"]["payload_hash"] == out["payload_hash"]
    assert app.jira.writes == []

    done = app.client.post(
        f"/api/v1/actions/{aid}/confirm", json={"payload_hash": out["payload_hash"]}, headers=ALICE
    )
    assert done.status_code == 200
    [write] = app.jira.writes
    fields = json.loads(write.content)["fields"]
    assert fields["summary"] == "Login com SSO"
    assert fields["priority"] == {"name": "High"}
    assert "Sessão expirada" in json.dumps(fields["description"], ensure_ascii=False)


@pytest.mark.req("F14-RT-01")
def test_salvar_sobre_versao_antiga_da_409(app: App) -> None:
    _, aid = app.propose()
    base = _card(app, aid)["payload_hash"]
    assert _save(app, aid, _edited(), base).status_code == 200

    again = _save(app, aid, pix_story_data(title="Outro"), base)

    assert again.status_code == 409
    assert again.json()["code"] == "action-changed"
    assert _card(app, aid)["preview"]["summary"] == "Login com SSO"


@pytest.mark.req("F14-RF-03")
def test_restaurar_volta_a_versao_do_agente(app: App) -> None:
    _, aid = app.propose()
    agent = _card(app, aid)
    saved = _save(app, aid, _edited(), agent["payload_hash"]).json()

    restored = app.client.post(
        f"/api/v1/actions/{aid}/restore", json={"base_hash": saved["payload_hash"]}, headers=ALICE
    )

    assert restored.status_code == 200
    out = restored.json()
    assert out["preview"]["summary"] == AGENT_TITLE
    assert out["payload_hash"] == agent["payload_hash"]
    assert (out["version"], out["edited_by"]) == (3, "agent")


@pytest.mark.req("F14-RT-02")
@pytest.mark.req("F14-RT-04")
def test_validacao_igual_a_da_ferramenta(app: App) -> None:
    _, aid = app.propose()
    base = _card(app, aid)["payload_hash"]

    assert _save(app, aid, pix_story_data(title=""), base).status_code == 422
    assert _save(app, aid, pix_story_data(title="x" * 256), base).status_code == 422
    epic = {"type": "epic", "title": "Pagamentos"}
    other_type = _save(app, aid, epic, base)
    assert other_type.status_code == 422
    assert other_type.json()["code"] == "action-not-editable"
    # Referência nova não entra pela edição (F19-RT-09).
    linked = pix_story_data(references=[{"title": "x", "url": "https://evil.example/wiki/1"}])
    out = _save(app, aid, linked, base).json()
    assert out["spec"]["references"] == []


@pytest.mark.req("F14-RT-05")
def test_so_a_dona_edita_e_so_pendente(app: App) -> None:
    _, aid = app.propose()
    base = _card(app, aid)["payload_hash"]
    body = {"spec": _edited(), "base_hash": base}

    assert app.client.put(f"/api/v1/actions/{aid}/spec", json=body, headers=BOB).status_code == 404
    preview = app.client.post(f"/api/v1/actions/{aid}/preview", json=body, headers=BOB)
    assert preview.status_code == 404

    app.client.post(f"/api/v1/actions/{aid}/reject", headers=ALICE)
    rejected = _save(app, aid, _edited(), base)
    assert (rejected.status_code, rejected.json()["code"]) == (409, "action-not-pending")


@pytest.mark.req("F14-RT-05")
def test_expirada_nao_edita(app: App) -> None:
    _, aid = app.propose()
    base = _card(app, aid)["payload_hash"]
    doc = app.store._action("uid-alice", aid)
    assert doc is not None
    doc["expiresAt"] = NOW - timedelta(minutes=1)

    assert _save(app, aid, _edited(), base).status_code == 410


@pytest.mark.req("F14-RF-02")
def test_confirmar_sem_hash_continua_valendo(app: App) -> None:
    """Clientes antigos confirmam sem corpo (F06): vale a versão atual."""
    _, aid = app.propose()
    assert app.client.post(f"/api/v1/actions/{aid}/confirm", headers=ALICE).status_code == 200
