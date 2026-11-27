"""Cliente do Jira: validar chave e criar projeto (F22-RF-02, F22-RT-03)."""

import json

import httpx
import pytest

from app.integrations.jira.client import (
    JiraClient,
    JiraForbiddenError,
    JiraUncertainError,
)

SITE = "https://exemplo.atlassian.net"


def _client(handler: httpx.MockTransport) -> JiraClient:
    async def no_sleep(_: float) -> None:
        return None

    return JiraClient(SITE, "po@teste.dev", "x" * 12, transport=handler, sleep=no_sleep)


@pytest.mark.req("F22-RF-02")
async def test_valida_e_sugere_chave() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.params["key"]
        if request.url.path.endswith("/validProjectKey"):
            return httpx.Response(200, json=f"{key}1")
        if key == "LOJA":
            return httpx.Response(
                200, json={"errorMessages": [], "errors": {"projectKey": "Key already in use."}}
            )
        return httpx.Response(200, json={"errorMessages": [], "errors": {}})

    async with _client(httpx.MockTransport(handler)) as jira:
        assert await jira.validate_project_key("NOVO") is None
        assert await jira.validate_project_key("LOJA") == "Key already in use."
        assert await jira.suggest_project_key("LOJA") == "LOJA1"


@pytest.mark.req("F22-RT-03")
async def test_cria_projeto_sem_repetir() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        body = json.loads(request.content)
        if body["key"] == "LENTO":
            return httpx.Response(503)
        if body["key"] == "NEGADO":
            return httpx.Response(403, json={"errorMessages": ["no permission"]})
        return httpx.Response(201, json={"id": 10001, "key": body["key"]})

    async with _client(httpx.MockTransport(handler)) as jira:
        created = await jira.create_project({"key": "NOVO", "name": "Novo"})
        assert (created.key, created.url) == ("NOVO", f"{SITE}/browse/NOVO")
        with pytest.raises(JiraUncertainError):
            await jira.create_project({"key": "LENTO", "name": "Lento"})
        with pytest.raises(JiraForbiddenError):
            await jira.create_project({"key": "NEGADO", "name": "Negado"})
    assert [r.url.path for r in sent] == ["/rest/api/3/project"] * 3  # o 503 não foi repetido
