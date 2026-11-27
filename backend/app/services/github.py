"""GitHub só leitura (F17, ADR-010): conexão por token fine-grained e vínculo com projetos.

O token chega em claro só no corpo do POST, é validado em `GET /user`, cifrado (KMS, ADR-004) e
descartado; nenhuma resposta nem log o contém (F17-RT-01). O vínculo projeto ↔ repositório é salvo
só depois de conferir que o token vê o repositório.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, SecretStr

from app.core.crypto import Cipher
from app.core.errors import ApiProblemError
from app.core.logging import uid_hash
from app.core.telemetry import in_thread
from app.integrations.github.client import (
    GitHubAuthError,
    GitHubClient,
    GitHubError,
    GitHubNotFoundError,
    GitHubRepo,
)

log = logging.getLogger("app.github")

ConnectionStatus = Literal["ok", "invalid"]
MAX_REPOS_OUT = 50


class GitHubConnectionInput(BaseModel):
    token: SecretStr = Field(min_length=20, max_length=255)


class GitHubConnectionOut(BaseModel):
    """Nunca o token: o login e os 4 últimos caracteres (F17-RT-01)."""

    id: str
    login: str
    token_hint: str
    status: ConnectionStatus
    last_validated_at: datetime


class RepoOut(BaseModel):
    full_name: str
    url: str
    default_branch: str
    private: bool
    description: str = ""


class RepoLinkOut(BaseModel):
    repo: RepoOut
    linked_at: datetime


class ProjectRepoOut(BaseModel):
    link: RepoLinkOut | None
    # `False` sem conexão GitHub: a tela manda conectar em Settings.
    connected: bool


class RepoLinkInput(BaseModel):
    full_name: str = Field(
        min_length=3, max_length=201, pattern=r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$"
    )


class GitHubInvalidTokenError(ApiProblemError):
    def __init__(self) -> None:
        super().__init__(
            422,
            "github-invalid-token",
            "Token recusado pelo GitHub",
            "O GitHub recusou o token. Confira se ele não expirou e tente de novo.",
        )


class GitHubUnreachableError(ApiProblemError):
    def __init__(self) -> None:
        super().__init__(
            502, "github-unreachable", "GitHub inacessível", "Não conseguimos falar com o GitHub."
        )


class GitHubConnectionExistsError(ApiProblemError):
    def __init__(self) -> None:
        super().__init__(
            409,
            "github-connection-exists",
            "Já existe uma conexão",
            "Você já conectou o GitHub. Remova a conexão atual para trocar o token.",
        )


class GitHubNotConnectedError(ApiProblemError):
    def __init__(self) -> None:
        super().__init__(
            409,
            "github-not-connected",
            "GitHub não conectado",
            "Conecte o GitHub em Settings antes de vincular um repositório.",
        )


class GitHubConnectionNotFoundError(ApiProblemError):
    def __init__(self) -> None:
        super().__init__(404, "github-connection-not-found", "Conexão não encontrada")


class RepoNotFoundError(ApiProblemError):
    def __init__(self) -> None:
        super().__init__(
            404,
            "github-repo-not-found",
            "Repositório não encontrado",
            "O token não vê esse repositório. Confira o nome e os repositórios do token no GitHub.",
        )


class GitHubStore(Protocol):
    def list_connections(self, uid: str) -> list[dict[str, Any]]: ...
    def create_connection(self, uid: str, data: dict[str, Any]) -> str: ...
    def update_connection(self, uid: str, connection_id: str, data: dict[str, Any]) -> None: ...
    def delete_connection(self, uid: str, connection_id: str) -> None: ...
    def get_link(self, uid: str, project_key: str) -> dict[str, Any] | None: ...
    def set_link(self, uid: str, project_key: str, data: dict[str, Any]) -> None: ...
    def delete_link(self, uid: str, project_key: str) -> None: ...


ClientFactory = Callable[[str], GitHubClient]


def _connection_out(doc: dict[str, Any]) -> GitHubConnectionOut:
    return GitHubConnectionOut(
        id=doc["id"],
        login=doc["login"],
        token_hint=doc["tokenHint"],
        status=doc["status"],
        last_validated_at=doc["lastValidatedAt"],
    )


def _repo_out(repo: GitHubRepo) -> RepoOut:
    return RepoOut(
        full_name=repo.full_name,
        url=repo.url,
        default_branch=repo.default_branch,
        private=repo.private,
        description=repo.description,
    )


def _link_out(doc: dict[str, Any]) -> RepoLinkOut:
    return RepoLinkOut(
        repo=RepoOut(
            full_name=doc["fullName"],
            url=doc["url"],
            default_branch=doc["defaultBranch"],
            private=bool(doc.get("private")),
        ),
        linked_at=doc["linkedAt"],
    )


class GitHubService:
    def __init__(
        self,
        store: GitHubStore,
        cipher: Cipher,
        client_factory: ClientFactory = GitHubClient,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._cipher = cipher
        self._client_factory = client_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _log(self, event: str, uid: str, **fields: Any) -> None:
        log.info(event, extra={"fields": {"event": event, "uid_hash": uid_hash(uid), **fields}})

    async def _connection(self, uid: str) -> dict[str, Any] | None:
        connections = await in_thread(self._store.list_connections, uid)
        return connections[0] if connections else None

    # ------------------------------------------------------------------ conexão (F17-RF-01)

    async def connections(self, uid: str) -> list[GitHubConnectionOut]:
        return [_connection_out(d) for d in await in_thread(self._store.list_connections, uid)]

    async def connect(self, uid: str, data: GitHubConnectionInput) -> GitHubConnectionOut:
        if await self._connection(uid) is not None:
            raise GitHubConnectionExistsError()
        token = data.token.get_secret_value()
        async with self._client_factory(token) as gh:
            try:
                user = await gh.user()
            except GitHubAuthError:
                raise GitHubInvalidTokenError() from None
            except GitHubError:
                raise GitHubUnreachableError() from None
        encrypted = await in_thread(self._cipher.encrypt, token)
        now = self._clock()
        doc = {
            "login": user.login,
            "tokenHint": token[-4:],
            "tokenCiphertext": encrypted.ciphertext,
            "kmsKeyVersion": encrypted.key_version,
            "status": "ok",
            "lastValidatedAt": now,
            "createdAt": now,
        }
        connection_id = await in_thread(self._store.create_connection, uid, doc)
        self._log("github_connected", uid)
        return _connection_out({"id": connection_id, **doc})

    async def validate(self, uid: str, connection_id: str) -> GitHubConnectionOut:
        current = await self._own(uid, connection_id)
        async with await self._client(current) as gh:
            try:
                user = await gh.user()
            except GitHubAuthError:
                return await self.mark_invalid(uid, current)
            except GitHubError:
                raise GitHubUnreachableError() from None
        fields = {"status": "ok", "login": user.login, "lastValidatedAt": self._clock()}
        await in_thread(self._store.update_connection, uid, connection_id, fields)
        return _connection_out({**current, **fields})

    async def mark_invalid(self, uid: str, current: dict[str, Any]) -> GitHubConnectionOut:
        await in_thread(self._store.update_connection, uid, current["id"], {"status": "invalid"})
        return _connection_out({**current, "status": "invalid"})

    async def disconnect(self, uid: str, connection_id: str) -> None:
        """Apaga a conexão e todos os vínculos (F17-RF-04)."""
        await self._own(uid, connection_id)
        await in_thread(self._store.delete_connection, uid, connection_id)
        self._log("github_disconnected", uid)

    async def _own(self, uid: str, connection_id: str) -> dict[str, Any]:
        current = await self._connection(uid)
        if current is None or current["id"] != connection_id:
            raise GitHubConnectionNotFoundError()
        return current

    async def _client(self, doc: dict[str, Any]) -> GitHubClient:
        token = await in_thread(self._cipher.decrypt, doc["tokenCiphertext"])
        return self._client_factory(token)

    async def client_for(self, uid: str) -> tuple[GitHubClient, dict[str, Any]] | None:
        """Cliente com o token decifrado só para esta requisição; `None` sem conexão válida."""
        current = await self._connection(uid)
        if current is None or current.get("status") != "ok":
            return None
        return await self._client(current), current

    # ------------------------------------------------------------------ repositórios e vínculo

    async def _connected_client(self, uid: str) -> tuple[GitHubClient, dict[str, Any]]:
        found = await self.client_for(uid)
        if found is None:
            raise GitHubNotConnectedError()
        return found

    async def repos(self, uid: str, query: str = "") -> list[RepoOut]:
        gh, current = await self._connected_client(uid)
        async with gh:
            try:
                repos = await gh.repos()
            except GitHubAuthError:
                await self.mark_invalid(uid, current)
                raise GitHubInvalidTokenError() from None
            except GitHubError:
                raise GitHubUnreachableError() from None
        needle = query.strip().lower()
        found = [r for r in repos if needle in r.full_name.lower()]
        return [_repo_out(r) for r in found[:MAX_REPOS_OUT]]

    async def project_repo(self, uid: str, project_key: str) -> ProjectRepoOut:
        connected = await self._connection(uid) is not None
        link = await in_thread(self._store.get_link, uid, project_key) if connected else None
        return ProjectRepoOut(link=_link_out(link) if link else None, connected=connected)

    async def link(self, uid: str, project_key: str, data: RepoLinkInput) -> RepoLinkOut:
        gh, current = await self._connected_client(uid)
        async with gh:
            try:
                repo = await gh.repo(data.full_name)
            except GitHubAuthError:
                await self.mark_invalid(uid, current)
                raise GitHubInvalidTokenError() from None
            except GitHubNotFoundError:
                raise RepoNotFoundError() from None
            except GitHubError:
                raise GitHubUnreachableError() from None
        doc = {
            "fullName": repo.full_name,
            "url": repo.url,
            "defaultBranch": repo.default_branch,
            "private": repo.private,
            "linkedAt": self._clock(),
        }
        await in_thread(self._store.set_link, uid, project_key, doc)
        self._log("repo_linked", uid, project_key=project_key)
        return _link_out(doc)

    async def unlink(self, uid: str, project_key: str) -> None:
        await in_thread(self._store.delete_link, uid, project_key)
        self._log("repo_unlinked", uid, project_key=project_key)

    async def linked(
        self, uid: str, project_key: str
    ) -> tuple[GitHubClient, dict[str, Any], dict[str, Any]] | None:
        """Para o chat (F17-RF-02): cliente, conexão e vínculo; `None` sem vínculo ou conexão."""
        link = await in_thread(self._store.get_link, uid, project_key)
        if link is None:
            return None
        found = await self.client_for(uid)
        if found is None:
            return None
        return found[0], found[1], link
