"""Leitor do repositório para o agente (F17): adapta o `GitHubClient` ao `RepoReader`.

A árvore é lida uma vez por turno; os arquivos, pelo tamanho que a árvore informa (F17-RT-03).
Token recusado chama `on_auth_error` (a conexão fica inválida, F17-RF-05). Os logs contam leituras,
nunca caminhos nem conteúdo.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.agent.tools.context import RepoEntry, RepoInfo, RepoToolError
from app.core.logging import uid_hash
from app.integrations.github.client import (
    FileTooLargeError,
    GitHubAuthError,
    GitHubClient,
    GitHubError,
    GitHubNotFoundError,
)

log = logging.getLogger("app.github")


class GitHubRepoReader:
    def __init__(
        self,
        client: GitHubClient,
        link: dict[str, Any],
        uid: str,
        on_auth_error: Callable[[], Awaitable[None]],
    ) -> None:
        self._client = client
        self._info = RepoInfo(
            full_name=str(link["fullName"]),
            url=str(link["url"]),
            default_branch=str(link["defaultBranch"]),
        )
        self._uid = uid
        self._on_auth_error = on_auth_error
        self._tree: tuple[list[RepoEntry], bool] | None = None
        self._sizes: dict[str, int] = {}
        self.reads = 0
        self.searches = 0

    @property
    def client(self) -> GitHubClient:
        return self._client

    @property
    def info(self) -> RepoInfo:
        return self._info

    async def _fail(self, exc: GitHubError) -> RepoToolError:
        if isinstance(exc, GitHubAuthError):
            await self._on_auth_error()
            return RepoToolError("o GitHub recusou o token; peça para reconectar em Settings")
        if isinstance(exc, FileTooLargeError):
            return RepoToolError("arquivo grande demais (mais de 100 KB)")
        if isinstance(exc, GitHubNotFoundError):
            return RepoToolError("não encontrado no repositório")
        return RepoToolError("o GitHub não respondeu; siga sem esse dado")

    async def entries(self) -> tuple[list[RepoEntry], bool]:
        if self._tree is None:
            try:
                tree = await self._client.tree(self._info.full_name, self._info.default_branch)
            except GitHubError as exc:
                raise await self._fail(exc) from None
            entries = [RepoEntry(e.path, e.type, e.size) for e in tree.entries]
            self._sizes = {e.path: e.size for e in entries if e.type == "blob"}
            self._tree = (entries, tree.truncated)
        return self._tree

    async def read(self, path: str) -> str:
        _, truncated = await self.entries()
        if path not in self._sizes and not truncated:
            raise RepoToolError("esse arquivo não existe no repositório")
        try:
            content = await self._client.file(
                self._info.full_name, path, self._info.default_branch, self._sizes.get(path)
            )
        except GitHubError as exc:
            raise await self._fail(exc) from None
        self.reads += 1
        return content

    async def search_code(self, text: str, limit: int) -> list[str]:
        self.searches += 1
        try:
            return await self._client.search_code(self._info.full_name, text, limit)
        except GitHubAuthError as exc:
            raise await self._fail(exc) from None
        except GitHubError:
            return []  # 10 req/min e só o branch padrão: a busca pelos caminhos já respondeu

    async def aclose(self) -> None:
        await self._client.aclose()

    def log_usage(self) -> None:
        if self.reads or self.searches:
            log.info(
                "repo_read",
                extra={
                    "fields": {
                        "event": "repo_read",
                        "uid_hash": uid_hash(self._uid),
                        "files": self.reads,
                        "searches": self.searches,
                    }
                },
            )
