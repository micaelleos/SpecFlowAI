"""Arquivos Spec Kit a partir das specs guardadas (F18-RF-01, F18-RF-03, F18-RF-05, F18-RT-03)."""

import httpx
import pytest

from app.agent.tools.context import RepoInfo, SpecExportError
from app.integrations.github.client import GitHubClient
from app.services.repo_reader import GitHubRepoReader
from app.services.spec_export import RepoSpecExporter, next_number, slug
from tests.chat_fakes import MemoryChatStore
from tests.export_fakes import UID, seed_epic
from tests.github_fake import VALID, FakeGitHub

LINK = {"fullName": "po/loja", "url": "https://github.com/po/loja", "defaultBranch": "main"}
SITE = "https://exemplo.atlassian.net"


async def _noop() -> None:
    return None


def _exporter(store: MemoryChatStore, github: FakeGitHub) -> RepoSpecExporter:
    client = GitHubClient(VALID, transport=httpx.MockTransport(github))
    reader = GitHubRepoReader(client, LINK, UID, _noop)
    assert reader.info == RepoInfo("po/loja", "https://github.com/po/loja", "main")
    return RepoSpecExporter(store, UID, reader, client, SITE)


def test_pasta_e_slug() -> None:
    assert (
        slug("Oferecer novos meios de pagamento no checkout")
        == "oferecer-novos-meios-de-pagamento-no"
    )
    assert slug("Ação & Reação!") == "acao-reacao"
    assert next_number({"src/a.py"}) == "001"
    assert next_number({"specs/001-a", "specs/017-b", "specs/017-b/spec.md", "specs/x"}) == "018"


@pytest.mark.req("F18-RF-01")
@pytest.mark.req("F18-RF-03")
@pytest.mark.req("F18-RT-03")
async def test_rascunho_com_spec_e_tasks() -> None:
    store, github = MemoryChatStore(), FakeGitHub()
    github.files["specs/004-antigo/spec.md"] = "# velho"
    seed_epic(store)

    draft = await _exporter(store, github).draft("abc-10")

    assert draft.kind == "create_pull_request"
    payload = draft.payload
    assert (payload["repo"], payload["base"], payload["branch"]) == (
        "po/loja",
        "main",
        "specflow/abc-10",
    )
    assert payload["issue_keys"] == ["ABC-10", "ABC-11", "ABC-12"]
    folder = "specs/005-oferecer-novos-meios-de-pagamento-no"
    spec, tasks = payload["files"]
    assert (spec["path"], tasks["path"]) == (f"{folder}/spec.md", f"{folder}/tasks.md")
    text = spec["content"]
    for heading in (
        "### Épico ABC-10",
        "### ABC-11 — Pagar com Pix",
        "### ABC-12 — Pagar com boleto",
    ):
        assert heading in text
    assert text.count("#### Objetivo") >= 3  # épico e cada história
    assert "#### Critérios de aceite" in text
    assert "#### Fora de escopo" in text
    assert "CA-01" in text
    assert f"[ABC-10]({SITE}/browse/ABC-10)" in text
    assert "ABC-50" not in text  # história de outro épico
    assert "- [ ] T001 [ABC-11] Pagar com Pix — critérios: CA-01" in tasks["content"]
    assert "T002 [ABC-12]" in tasks["content"]
    assert draft.preview["files"] == payload["files"]
    assert all(r.method == "GET" for r in github.requests)  # nada escrito na proposta


@pytest.mark.req("F18-RT-02")
async def test_branch_existente_ganha_sufixo() -> None:
    store, github = MemoryChatStore(), FakeGitHub()
    github.branches |= {"specflow/abc-10", "specflow/abc-10-2"}
    seed_epic(store)
    draft = await _exporter(store, github).draft("ABC-10")
    assert draft.payload["branch"] == "specflow/abc-10-3"


@pytest.mark.req("F18-RF-05")
async def test_so_epicos_do_specflow_com_historias() -> None:
    store, github = MemoryChatStore(), FakeGitHub()
    seed_epic(store, stories=0)
    exporter = _exporter(store, github)
    with pytest.raises(SpecExportError, match="não é um épico criado pelo SpecFlow"):
        await exporter.draft("ABC-77")
    with pytest.raises(SpecExportError, match="não é um épico"):
        await exporter.draft("ABC-50")  # história, não épico
    with pytest.raises(SpecExportError, match="não tem histórias"):
        await exporter.draft("ABC-10")
