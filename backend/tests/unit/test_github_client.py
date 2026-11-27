"""Cliente do GitHub (F17-RT-02, F17-RT-03): host fixo, só leitura, limites e erros."""

import httpx
import pytest

from app.integrations.github.client import (
    MAX_FILE_BYTES,
    FileTooLargeError,
    GitHubAuthError,
    GitHubClient,
    GitHubForbiddenError,
    GitHubNotFoundError,
    GitHubUnreachableError,
    valid_path,
    valid_repo_name,
)

TOKEN = "github_pat_segredo_1234"


def _client(handler: httpx.MockTransport) -> GitHubClient:
    return GitHubClient(TOKEN, transport=handler)


@pytest.mark.req("F17-RT-02")
async def test_cabecalhos_host_fixo_e_so_get() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"login": "po", "name": None})

    async with _client(httpx.MockTransport(handler)) as gh:
        user = await gh.user()

    assert (user.login, user.name) == ("po", "po")
    [request] = seen
    assert request.method == "GET"
    assert str(request.url) == "https://api.github.com/user"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"


@pytest.mark.req("F17-RT-02")
@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, GitHubAuthError),
        (403, GitHubForbiddenError),
        (404, GitHubNotFoundError),
        (301, GitHubNotFoundError),  # redirecionamento não é seguido
        (503, GitHubUnreachableError),
    ],
)
async def test_erros(status: int, error: type[Exception]) -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(status, headers={"Location": "x"}))
    async with _client(transport) as gh:
        with pytest.raises(error) as raised:
            await gh.repo("po/loja")
    assert TOKEN not in str(raised.value)


@pytest.mark.req("F17-RT-03")
async def test_arquivo_cru_e_limite_de_tamanho() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Accept"] == "application/vnd.github.raw+json"
        assert request.url.params["ref"] == "main"
        if request.url.path.endswith("grande.txt"):
            return httpx.Response(200, content=b"x" * (MAX_FILE_BYTES + 1))
        return httpx.Response(200, content="# Instruções\nRode `make test`.".encode())

    async with _client(httpx.MockTransport(handler)) as gh:
        assert "make test" in await gh.file("po/loja", "AGENTS.md", "main")
        with pytest.raises(FileTooLargeError):
            await gh.file("po/loja", "grande.txt", "main")
        with pytest.raises(FileTooLargeError):
            await gh.file("po/loja", "outro.bin", "main", size=MAX_FILE_BYTES + 1)
        with pytest.raises(GitHubNotFoundError):
            await gh.file("po/loja", "../../user", "main")


async def test_arvore_e_busca() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/po/loja/git/trees/main":
            assert request.url.params["recursive"] == "1"
            tree = [
                {"path": "src", "type": "tree"},
                {"path": "src/cadastro.py", "type": "blob", "size": 10},
                {"path": "lib", "type": "commit"},  # submódulo: fora
            ]
            return httpx.Response(200, json={"tree": tree, "truncated": False})
        assert request.url.params["q"] == "cpf repo:po/loja"
        return httpx.Response(200, json={"items": [{"path": "src/cadastro.py"}]})

    async with _client(httpx.MockTransport(handler)) as gh:
        tree = await gh.tree("po/loja", "main")
        assert [e.path for e in tree.entries] == ["src", "src/cadastro.py"]
        assert await gh.search_code("po/loja", "cpf", 5) == ["src/cadastro.py"]


def test_nomes_e_caminhos_validos() -> None:
    assert valid_repo_name("po/loja-online")
    assert not valid_repo_name("po/../x")
    assert not valid_repo_name("https://evil/x")
    assert valid_path("src/app/main.py")
    for bad in ("", "/etc/passwd", "a/../b", "a//b", "a\nb"):
        assert not valid_path(bad)
