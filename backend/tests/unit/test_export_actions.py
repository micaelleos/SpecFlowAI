"""O PR com as specs depois do Confirm (F18-RF-02, F18-RF-04, F18-RF-05, F18-RT-01/02/04)."""

import logging
from typing import Any, cast

import pytest

from app.core.config import Settings
from app.services.actions import ActionFailedError, ActionService
from app.services.jira_connections import JiraConnectionService
from tests.chat_fakes import NOW, FakeJiraService, MemoryChatStore
from tests.export_fakes import UID, GitHubLinks, jira_with_remote_links
from tests.unit.test_export_tools import _turn


async def _proposed(
    links: GitHubLinks, jira_status: int = 201
) -> tuple[MemoryChatStore, ActionService, dict[str, Any], list[dict[str, Any]]]:
    store, _, _ = await _turn(links)
    [doc] = [a for a in store.actions[UID] if a.get("kind") == "create_pull_request"]
    handler, remote = jira_with_remote_links(jira_status)
    service = ActionService(
        store,
        cast(JiraConnectionService, FakeJiraService(handler=handler)),
        Settings(env="test"),
        clock=lambda: NOW,
        github=links,
    )
    return store, service, doc, remote


@pytest.mark.req("F18-RF-02")
@pytest.mark.req("F18-RF-04")
@pytest.mark.req("F18-RT-02")
@pytest.mark.req("F18-RT-04")
async def test_confirmar_abre_o_pr_e_liga_o_epico(caplog: pytest.LogCaptureFixture) -> None:
    links = GitHubLinks()
    store, service, doc, remote = await _proposed(links)

    with caplog.at_level(logging.INFO, logger="app.actions"):
        out = await service.confirm(UID, doc["id"], payload_hash=doc["payloadHash"])

    assert out.status == "done"
    assert out.result is not None
    assert out.result.model_dump() == {
        "issue_key": "#1",
        "url": "https://github.com/po/loja/pull/1",
    }
    gh = links.github
    assert gh.branches == {"specflow/abc-10"}
    assert set(gh.written) == {"specflow/abc-10"}  # nada em main
    assert sorted(gh.written["specflow/abc-10"]) == [f["path"] for f in doc["payload"]["files"]]
    [pull] = gh.pulls
    assert (pull["head"], pull["base"]) == ("specflow/abc-10", "main")
    [link] = remote
    assert link["path"] == "/rest/api/3/issue/ABC-10/remotelink"
    assert link["object"]["url"] == "https://github.com/po/loja/pull/1"
    [audit] = [r for r in caplog.records if r.getMessage() == "github_write"]
    fields = cast(dict[str, Any], audit.__dict__["fields"])
    assert (fields["repo"], fields["pr"], fields["result"]) == ("po/loja", 1, "done")
    assert "specs" not in str(fields)  # sem conteúdo
    [message] = [
        m for k, ms in store.messages.items() for m in ms if m.get("actionId") == doc["id"]
    ]
    assert "abriu o PR #1" in message["content"]


@pytest.mark.req("F18-RF-04")
async def test_link_no_jira_falha_vira_aviso() -> None:
    links = GitHubLinks()
    store, service, doc, _ = await _proposed(links, jira_status=403)
    out = await service.confirm(UID, doc["id"])
    assert out.status == "done"
    assert links.github.pulls
    saved = store.get_action(UID, doc["id"])
    assert saved is not None
    assert out.result is not None
    assert "não foi criado no Jira" in (out.result.warning or "")
    assert "não foi criado no Jira" in saved["result"]["warning"]


@pytest.mark.req("F18-RF-05")
async def test_sem_permissao_de_escrita() -> None:
    links = GitHubLinks()
    _, service, doc, remote = await _proposed(links)
    links.github.write_status = 403
    with pytest.raises(ActionFailedError) as failed:
        await service.confirm(UID, doc["id"])
    assert failed.value.code == "github-write-forbidden"
    assert "Contents: Read and write" in (failed.value.detail or "")
    assert links.github.pulls == []
    assert remote == []


@pytest.mark.req("F18-RT-01")
@pytest.mark.req("F18-RT-02")
async def test_payload_alterado_ou_branch_padrao_nao_executa() -> None:
    links = GitHubLinks()
    store, service, doc, _ = await _proposed(links)
    for action in store.actions[UID]:
        if action["id"] == doc["id"]:
            action["payload"]["branch"] = "main"
    with pytest.raises(ActionFailedError) as failed:
        await service.confirm(UID, doc["id"])
    assert failed.value.code == "action-integrity"
    assert links.github.branches == set()
    assert links.github.written == {}
