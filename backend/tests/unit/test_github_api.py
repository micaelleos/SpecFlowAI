"""Conexão GitHub e vínculo projeto ↔ repositório pela API (F17-RF-01, F17-RF-04, F17-RT-01)."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_github_service, get_verifier
from app.core.config import Settings, get_settings
from app.core.crypto import LocalFernetCipher
from app.main import create_app
from app.services.github import GitHubService
from tests.chat_fakes import NOW
from tests.fakes import FakeVerifier, MemoryGitHubStore
from tests.github_fake import VALID, FakeGitHub

ALICE = {"Authorization": "Bearer ok:alice"}
BOB = {"Authorization": "Bearer ok:bob"}


@dataclass
class Api:
    client: TestClient
    store: MemoryGitHubStore
    github: FakeGitHub

    def connect(self, token: str = VALID, headers: dict[str, str] = ALICE) -> Any:
        return self.client.post(
            "/api/v1/github/connections", json={"token": token}, headers=headers
        )


@pytest.fixture
def api() -> Iterator[Api]:
    store, github = MemoryGitHubStore(), FakeGitHub()
    service = GitHubService(store, LocalFernetCipher(), github.factory(), clock=lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(env="test")
    app.dependency_overrides[get_verifier] = FakeVerifier
    app.dependency_overrides[get_github_service] = lambda: service
    with TestClient(app) as client:
        yield Api(client, store, github)


@pytest.mark.req("F17-RF-01")
@pytest.mark.req("F17-RT-01")
def test_conecta_sem_devolver_nem_guardar_o_token_em_claro(
    api: Api, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        response = api.connect()

    assert response.status_code == 201
    body = response.json()
    assert (body["login"], body["token_hint"], body["status"]) == ("po", "abcd", "ok")
    assert VALID not in response.text
    [stored] = api.store.connections["uid-alice"].values()
    assert VALID.encode() not in stored["tokenCiphertext"]
    assert VALID not in str(stored)
    assert VALID not in caplog.text
    listed = api.client.get("/api/v1/github/connections", headers=ALICE).json()
    assert [c["login"] for c in listed] == ["po"]
    assert api.client.get("/api/v1/github/connections", headers=BOB).json() == []


@pytest.mark.req("F17-RF-01")
def test_token_recusado_nao_salva(api: Api) -> None:
    response = api.connect("github_pat_errado_000000000000")
    assert response.status_code == 422
    assert response.json()["code"] == "github-invalid-token"
    assert api.store.connections == {}
    assert api.connect().status_code == 201
    assert api.connect().status_code == 409


@pytest.mark.req("F17-RF-01")
def test_lista_repos_e_vincula_so_o_que_o_token_ve(api: Api) -> None:
    sem = api.client.put(
        "/api/v1/jira/projects/ABC/repo", json={"full_name": "po/loja"}, headers=ALICE
    )
    assert (sem.status_code, sem.json()["code"]) == (409, "github-not-connected")
    assert api.client.get("/api/v1/jira/projects/ABC/repo", headers=ALICE).json() == {
        "link": None,
        "connected": False,
    }
    api.connect()

    repos = api.client.get("/api/v1/github/repos?q=loj", headers=ALICE).json()
    assert [r["full_name"] for r in repos] == ["po/loja"]

    linked = api.client.put(
        "/api/v1/jira/projects/ABC/repo", json={"full_name": "po/loja"}, headers=ALICE
    )
    assert linked.status_code == 200
    assert linked.json()["repo"]["default_branch"] == "main"
    got = api.client.get("/api/v1/jira/projects/ABC/repo", headers=ALICE).json()
    assert got["link"]["repo"]["full_name"] == "po/loja"

    other = api.client.put(
        "/api/v1/jira/projects/ABC/repo", json={"full_name": "outra/coisa"}, headers=ALICE
    )
    assert (other.status_code, other.json()["code"]) == (404, "github-repo-not-found")
    before = len(api.github.requests)
    bad = api.client.put(
        "/api/v1/jira/projects/FIN/repo", json={"full_name": "../x"}, headers=ALICE
    )
    assert bad.status_code == 404
    assert ("uid-alice", "FIN") not in api.store.links
    assert not [r for r in api.github.requests[before:] if ".." in r.url.path]


@pytest.mark.req("F17-RF-04")
def test_desvincular_e_desconectar_apaga_os_vinculos(api: Api) -> None:
    cid = api.connect().json()["id"]
    for key in ("ABC", "FIN"):
        api.client.put(
            f"/api/v1/jira/projects/{key}/repo", json={"full_name": "po/loja"}, headers=ALICE
        )

    assert api.client.delete("/api/v1/jira/projects/ABC/repo", headers=ALICE).status_code == 204
    assert ("uid-alice", "ABC") not in api.store.links
    assert ("uid-alice", "FIN") in api.store.links

    assert api.client.delete(f"/api/v1/github/connections/{cid}", headers=BOB).status_code == 404
    assert api.client.delete(f"/api/v1/github/connections/{cid}", headers=ALICE).status_code == 204
    assert api.store.links == {}
    assert api.store.connections["uid-alice"] == {}


@pytest.mark.req("F17-RF-05")
def test_validar_token_revogado_marca_invalida(api: Api) -> None:
    cid = api.connect().json()["id"]
    api.store.connections["uid-alice"][cid]["tokenCiphertext"] = (
        LocalFernetCipher().encrypt("github_pat_revogado_00000000000").ciphertext
    )
    response = api.client.post(f"/api/v1/github/connections/{cid}/validate", headers=ALICE)
    assert response.json()["status"] == "invalid"
