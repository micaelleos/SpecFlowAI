"""Escrita no GitHub (F18-RF-02, F18-RT-02): só branch specflow/*, sem repetir; link no Jira."""

import base64
import json

import httpx
import pytest

from app.integrations.github.client import (
    GitHubClient,
    GitHubConflictError,
    GitHubForbiddenError,
    GitHubUncertainError,
)
from app.integrations.jira.client import JiraClient

TOKEN = "github_pat_escrita_000000000000"


def _gh(handler: httpx.MockTransport) -> GitHubClient:
    return GitHubClient(TOKEN, transport=handler)


@pytest.mark.req("F18-RF-02")
@pytest.mark.req("F18-RT-02")
async def test_branch_arquivo_e_pr() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path == "/repos/po/loja/git/ref/heads/main":
            return httpx.Response(200, json={"object": {"sha": "abc123"}})
        if path == "/repos/po/loja/git/ref/heads/specflow/abc-10":
            return httpx.Response(404, json={"message": "Not Found"})
        if path == "/repos/po/loja/git/refs":
            return httpx.Response(201, json={})
        if path.startswith("/repos/po/loja/contents/"):
            return httpx.Response(201, json={})
        if path == "/repos/po/loja/pulls":
            return httpx.Response(
                201, json={"number": 7, "html_url": "https://github.com/po/loja/pull/7"}
            )
        raise AssertionError(path)

    async with _gh(httpx.MockTransport(handler)) as gh:
        assert await gh.branch_sha("po/loja", "main") == "abc123"
        assert await gh.branch_sha("po/loja", "specflow/abc-10") is None
        await gh.create_branch("po/loja", "specflow/abc-10", "abc123")
        await gh.put_file("po/loja", "specflow/abc-10", "specs/001-pix/spec.md", "# Pix", "docs")
        pr = await gh.create_pull("po/loja", "specflow/abc-10", "main", "Specs", "corpo")

    assert (pr.number, pr.url) == (7, "https://github.com/po/loja/pull/7")
    ref, put, pull = seen[2:]
    assert json.loads(ref.content) == {"ref": "refs/heads/specflow/abc-10", "sha": "abc123"}
    body = json.loads(put.content)
    assert put.method == "PUT"
    assert body["branch"] == "specflow/abc-10"
    assert base64.b64decode(body["content"]).decode() == "# Pix"
    assert json.loads(pull.content)["base"] == "main"


@pytest.mark.req("F18-RT-02")
async def test_nunca_escreve_fora_de_specflow_nem_repete() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/pulls"):
            return httpx.Response(503)
        if request.url.path.endswith("/refs"):
            return httpx.Response(422, json={"message": "Reference already exists"})
        return httpx.Response(403, json={"message": "Resource not accessible"})

    async with _gh(httpx.MockTransport(handler)) as gh:
        with pytest.raises(GitHubConflictError):
            await gh.create_branch("po/loja", "main", "abc")
        with pytest.raises(GitHubConflictError):
            await gh.put_file("po/loja", "main", "README.md", "x", "m")
        with pytest.raises(GitHubConflictError):
            await gh.put_file("po/loja", "specflow/x", "../x", "x", "m")
        assert calls == []  # nada enviado
        with pytest.raises(GitHubConflictError, match="already exists"):
            await gh.create_branch("po/loja", "specflow/x", "abc")
        with pytest.raises(GitHubForbiddenError):
            await gh.put_file("po/loja", "specflow/x", "specs/a.md", "x", "m")
        with pytest.raises(GitHubUncertainError):
            await gh.create_pull("po/loja", "specflow/x", "main", "t", "b")
    assert calls.count("/repos/po/loja/pulls") == 1


@pytest.mark.req("F18-RF-04")
async def test_link_remoto_no_jira() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(201, json={"id": 1})

    async with JiraClient(
        "https://exemplo.atlassian.net",
        "po@teste.dev",
        "x" * 12,
        transport=httpx.MockTransport(handler),
    ) as jira:
        await jira.add_remote_link("ABC-10", "https://github.com/po/loja/pull/7", "PR #7")
    [request] = sent
    assert request.url.path == "/rest/api/3/issue/ABC-10/remotelink"
    assert json.loads(request.content)["object"]["url"] == "https://github.com/po/loja/pull/7"
