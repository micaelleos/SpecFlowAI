"""GitHub simulado para os testes da F17: um repositório `po/loja` com instruções e código."""

import base64
import json
from collections.abc import Callable

import httpx

from app.integrations.github.client import GitHubClient

VALID = "github_pat_valido_0000000000abcd"
FILES: dict[str, str] = {
    "AGENTS.md": "# Loja\nTestes: rode `make test`. Código em `src/`.",
    "Makefile": "test:\n\tpytest\n",
    "src/cadastro/cpf.py": "def validar_cpf(cpf: str) -> bool:\n    ...\n",
    "src/cadastro/views.py": "from .cpf import validar_cpf\n",
    "src/pedidos/checkout.py": "def pagar(): ...\n",
    "tests/test_cpf.py": "def test_cpf(): ...\n",
}


class FakeGitHub:
    def __init__(self, files: dict[str, str] | None = None) -> None:
        self.files = dict(FILES if files is None else files)
        self.requests: list[httpx.Request] = []
        self.search_fails = False
        # F18: escrita (branches criadas, arquivos gravados, PRs) e uma recusa opcional (403).
        self.branches: set[str] = set()
        self.written: dict[str, dict[str, str]] = {}
        self.pulls: list[dict[str, str]] = []
        self.write_status: int | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("Authorization") != f"Bearer {VALID}":
            return httpx.Response(401, json={"message": "Bad credentials"})
        path = request.url.path
        repo = {
            "full_name": "po/loja",
            "default_branch": "main",
            "private": True,
            "html_url": "https://github.com/po/loja",
            "description": "Loja online",
        }
        if path == "/user":
            return httpx.Response(200, json={"login": "po", "name": "PO"})
        if path == "/user/repos":
            other = {**repo, "full_name": "po/blog", "html_url": "https://github.com/po/blog"}
            return httpx.Response(200, json=[repo, other])
        if path == "/repos/po/loja":
            return httpx.Response(200, json=repo)
        if path == "/repos/po/loja/git/trees/main":
            dirs = {
                "/".join(p.split("/")[:i]) for p in self.files for i in range(1, p.count("/") + 1)
            }
            tree = [{"path": d, "type": "tree"} for d in sorted(dirs)] + [
                {"path": p, "type": "blob", "size": len(c)} for p, c in self.files.items()
            ]
            return httpx.Response(200, json={"tree": tree, "truncated": False})
        if path.startswith("/repos/po/loja/git/ref/heads/"):
            branch = path.removeprefix("/repos/po/loja/git/ref/heads/")
            if branch == "main" or branch in self.branches:
                return httpx.Response(200, json={"object": {"sha": f"sha-{branch}"}})
            return httpx.Response(404, json={"message": "Not Found"})
        if request.method in ("POST", "PUT") and self.write_status is not None:
            return httpx.Response(self.write_status, json={"message": "Resource not accessible"})
        if path == "/repos/po/loja/git/refs" and request.method == "POST":
            branch = json.loads(request.content)["ref"].removeprefix("refs/heads/")
            if branch in self.branches:
                return httpx.Response(422, json={"message": "Reference already exists"})
            self.branches.add(branch)
            return httpx.Response(201, json={})
        if path.startswith("/repos/po/loja/contents/") and request.method == "PUT":
            body = json.loads(request.content)
            name = path.removeprefix("/repos/po/loja/contents/")
            content = base64.b64decode(body["content"]).decode()
            self.written.setdefault(body["branch"], {})[name] = content
            return httpx.Response(201, json={})
        if path == "/repos/po/loja/pulls" and request.method == "POST":
            self.pulls.append(json.loads(request.content))
            n = len(self.pulls)
            return httpx.Response(
                201, json={"number": n, "html_url": f"https://github.com/po/loja/pull/{n}"}
            )
        if path.startswith("/repos/po/loja/contents/"):
            name = path.removeprefix("/repos/po/loja/contents/")
            if name in self.files:
                return httpx.Response(200, content=self.files[name].encode())
            return httpx.Response(404, json={"message": "Not Found"})
        if path == "/search/code":
            if self.search_fails:
                return httpx.Response(403, json={"message": "rate limit"})
            text = request.url.params["q"].split(" repo:")[0].lower()
            items = [{"path": p} for p, c in self.files.items() if text in c.lower()]
            return httpx.Response(200, content=json.dumps({"items": items}).encode())
        return httpx.Response(404, json={"message": "Not Found"})

    def factory(self) -> Callable[[str], GitHubClient]:
        return lambda token: GitHubClient(token, transport=httpx.MockTransport(self))
