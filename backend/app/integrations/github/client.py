"""Cliente HTTP do GitHub, só leitura, com token fine-grained (F17, ADR-010).

Uma instância por requisição e por usuário: o token chega decifrado do serviço e vive só aqui.
O host é fixo (`api.github.com`): nenhuma URL vem do usuário (F17-RT-02). Nada é escrito.
"""

import asyncio
import re
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx

API = "https://api.github.com"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
MAX_ATTEMPTS = 2
MAX_FILE_BYTES = 100_000  # F17-RT-03
MAX_REPOS = 100
_RETRY_STATUS = {500, 502, 503, 504}
REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")


class GitHubError(Exception):
    """Erro ao falar com o GitHub. Mensagens nunca incluem o token."""


class GitHubAuthError(GitHubError):
    """O GitHub recusou o token (401)."""


class GitHubNotFoundError(GitHubError):
    """Repositório ou arquivo inexistente, ou fora do alcance do token (o GitHub responde 404)."""


class GitHubForbiddenError(GitHubError):
    """403: sem permissão ou limite de requisições esgotado."""


class GitHubUnreachableError(GitHubError):
    """GitHub fora do ar ou lento demais depois das tentativas."""


class FileTooLargeError(GitHubError):
    """Arquivo acima de `MAX_FILE_BYTES`: não é lido (F17-RT-03)."""


@dataclass(frozen=True)
class GitHubUser:
    login: str
    name: str


@dataclass(frozen=True)
class GitHubRepo:
    full_name: str
    default_branch: str
    private: bool
    url: str
    description: str = ""


@dataclass(frozen=True)
class TreeEntry:
    path: str
    type: str  # "blob" (arquivo) ou "tree" (pasta)
    size: int = 0


@dataclass(frozen=True)
class Tree:
    entries: list[TreeEntry]
    truncated: bool


def valid_path(path: str) -> bool:
    """Caminho relativo dentro do repositório: sem `..`, sem barra inicial, sem controle."""
    parts = path.split("/")
    return (
        0 < len(path) <= 500
        and not path.startswith("/")
        and all(p not in ("", ".", "..") for p in parts)
        and not any(ord(c) < 32 for c in path)
    )


def valid_repo_name(full_name: str) -> bool:
    return bool(REPO_NAME.match(full_name)) and ".." not in full_name


def _repo(data: dict[str, Any]) -> GitHubRepo:
    return GitHubRepo(
        full_name=str(data["full_name"]),
        default_branch=str(data.get("default_branch") or "main"),
        private=bool(data.get("private")),
        url=str(data.get("html_url") or f"https://github.com/{data['full_name']}"),
        description=str(data.get("description") or ""),
    )


class GitHubClient:
    def __init__(self, token: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._http = httpx.AsyncClient(
            base_url=API,
            timeout=TIMEOUT,
            follow_redirects=False,
            transport=transport,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "specflow-ai",
            },
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(
        self, path: str, params: dict[str, Any] | None = None, accept: str | None = None
    ) -> httpx.Response:
        headers = {"Accept": accept} if accept else None
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = await self._http.get(path, params=params, headers=headers)
            except httpx.HTTPError:
                if attempt + 1 == MAX_ATTEMPTS:
                    raise GitHubUnreachableError("GitHub inacessível") from None
                continue
            if response.status_code in _RETRY_STATUS and attempt + 1 < MAX_ATTEMPTS:
                await asyncio.sleep(0.5)
                continue
            break
        if response.status_code == 401:
            raise GitHubAuthError("O GitHub recusou o token")
        if response.status_code == 403 or response.status_code == 429:
            raise GitHubForbiddenError("Sem permissão no GitHub ou limite de requisições")
        if response.status_code in (301, 302, 307, 404, 409, 422):
            raise GitHubNotFoundError("Não encontrado no GitHub")
        if response.status_code >= 400:
            raise GitHubUnreachableError(f"GitHub respondeu {response.status_code}")
        return response

    async def user(self) -> GitHubUser:
        data = (await self._get("/user")).json()
        return GitHubUser(login=str(data["login"]), name=str(data.get("name") or data["login"]))

    async def repos(self) -> list[GitHubRepo]:
        """Repositórios que o token vê (até 100, os mais recentes primeiro)."""
        params = {"per_page": MAX_REPOS, "sort": "pushed"}
        return [_repo(r) for r in (await self._get("/user/repos", params)).json()]

    async def repo(self, full_name: str) -> GitHubRepo:
        if not valid_repo_name(full_name):
            raise GitHubNotFoundError("Nome de repositório inválido")
        return _repo((await self._get(f"/repos/{full_name}")).json())

    async def tree(self, full_name: str, ref: str) -> Tree:
        """Árvore inteira do branch (recursiva); `truncated` em repositórios enormes."""
        data = (
            await self._get(f"/repos/{full_name}/git/trees/{quote(ref, safe='')}", {"recursive": 1})
        ).json()
        entries = [
            TreeEntry(path=str(e["path"]), type=str(e["type"]), size=int(e.get("size") or 0))
            for e in data.get("tree", [])
            if e.get("type") in ("blob", "tree")
        ]
        return Tree(entries=entries, truncated=bool(data.get("truncated")))

    async def file(self, full_name: str, path: str, ref: str, size: int | None = None) -> str:
        """Conteúdo do arquivo (texto), até `MAX_FILE_BYTES`."""
        if not valid_path(path):
            raise GitHubNotFoundError("Caminho inválido")
        if size is not None and size > MAX_FILE_BYTES:
            raise FileTooLargeError("Arquivo grande demais")
        response = await self._get(
            f"/repos/{full_name}/contents/{quote(path)}",
            {"ref": ref},
            accept="application/vnd.github.raw+json",
        )
        if len(response.content) > MAX_FILE_BYTES:
            raise FileTooLargeError("Arquivo grande demais")
        return response.content.decode("utf-8", errors="replace")

    async def search_code(self, full_name: str, text: str, limit: int) -> list[str]:
        """Caminhos que contêm o texto (busca de código: só o branch padrão, 10 req/min)."""
        query = f"{text} repo:{full_name}"
        data = (await self._get("/search/code", {"q": query, "per_page": limit})).json()
        return [str(item["path"]) for item in data.get("items", [])][:limit]
