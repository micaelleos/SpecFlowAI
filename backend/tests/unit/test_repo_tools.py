"""Leitura do repositório pelo agente (F17-RF-02, F17-RF-03, F17-RT-03)."""

from typing import Any, cast

import httpx
import pytest
from langchain_core.runnables import RunnableConfig

from app.agent.tools.context import ToolContext
from app.agent.tools.repo_tools import (
    MAX_FILES_PER_TURN,
    NO_REPO,
    buscar_no_repositorio,
    ler_arquivo_do_repositorio,
    listar_arquivos_do_repositorio,
    repo_note,
)
from app.integrations.github.client import MAX_FILE_BYTES, GitHubClient
from app.services.repo_reader import GitHubRepoReader
from tests.github_fake import VALID, FakeGitHub

LINK = {"fullName": "po/loja", "url": "https://github.com/po/loja", "defaultBranch": "main"}


class Setup:
    def __init__(self, files: dict[str, str] | None = None, token: str = VALID) -> None:
        self.github = FakeGitHub(files)
        self.invalidated = 0
        client = GitHubClient(token, transport=httpx.MockTransport(self.github))

        async def invalid() -> None:
            self.invalidated += 1

        self.reader = GitHubRepoReader(client, LINK, "uid-alice", invalid)
        self.ctx = ToolContext("uid-alice", "c1", None, cast(Any, None), repo=self.reader)

    @property
    def config(self) -> RunnableConfig:
        return {"configurable": {"ctx": self.ctx}}


async def _call(tool: Any, args: dict[str, Any], config: RunnableConfig) -> str:
    return str(await tool.ainvoke(args, config=config))


@pytest.mark.req("F17-RF-02")
@pytest.mark.req("F17-RT-03")
async def test_nota_traz_instrucoes_e_raiz_como_dado() -> None:
    note = await repo_note(Setup().reader)

    assert "po/loja (branch main)" in note
    assert "make test" in note  # do AGENTS.md
    assert '<dados_repositorio confiavel="nao">' in note
    for entry in ("AGENTS.md", "Makefile", "src/", "tests/"):
        assert f'"{entry}"' in note
    assert "Nunca invente caminhos" in note


@pytest.mark.req("F17-RF-02")
async def test_nota_usa_claude_md_e_copilot_quando_nao_ha_agents() -> None:
    note = await repo_note(Setup({".github/copilot-instructions.md": "Use pnpm test."}).reader)
    assert "Use pnpm test." in note
    assert "sem AGENTS.md" not in note
    assert "sem AGENTS.md" in await repo_note(Setup({"src/a.py": "x"}).reader)


@pytest.mark.req("F17-RF-03")
async def test_listar_buscar_e_ler() -> None:
    s = Setup()
    listed = await _call(listar_arquivos_do_repositorio, {"pasta": "src"}, s.config)
    assert '"src/cadastro/"' in listed
    assert '"src/pedidos/"' in listed
    assert "não existe" in await _call(listar_arquivos_do_repositorio, {"pasta": "x"}, s.config)

    found = await _call(buscar_no_repositorio, {"texto": "cpf"}, s.config)
    assert "src/cadastro/cpf.py" in found
    assert "tests/test_cpf.py" in found
    by_content = await _call(buscar_no_repositorio, {"texto": "validar_cpf"}, s.config)
    assert "src/cadastro/views.py" in by_content  # só a busca de código acha
    s.github.search_fails = True  # 10 req/min: a busca pelos caminhos responde sozinha
    assert "src/cadastro/cpf.py" in await _call(buscar_no_repositorio, {"texto": "cpf"}, s.config)

    read = await _call(ler_arquivo_do_repositorio, {"caminho": "./src/cadastro/cpf.py"}, s.config)
    assert "def validar_cpf" in read
    assert '<dados_repositorio confiavel="nao">' in read
    missing = await _call(ler_arquivo_do_repositorio, {"caminho": "src/nada.py"}, s.config)
    assert "não existe" in missing


@pytest.mark.req("F17-RT-03")
async def test_limites_de_leitura() -> None:
    files = {f"f{i}.py": "x" for i in range(MAX_FILES_PER_TURN + 1)}
    files["grande.json"] = "x" * (MAX_FILE_BYTES + 1)
    files[".github/workflows/ci.yml"] = "run: make test"
    s = Setup(files)
    assert "grande demais" in await _call(
        ler_arquivo_do_repositorio, {"caminho": "grande.json"}, s.config
    )
    assert "make test" in await _call(
        ler_arquivo_do_repositorio, {"caminho": ".github/workflows/ci.yml"}, s.config
    )
    for i in range(MAX_FILES_PER_TURN - 1):
        await _call(ler_arquivo_do_repositorio, {"caminho": f"f{i}.py"}, s.config)
    last = await _call(ler_arquivo_do_repositorio, {"caminho": "f20.py"}, s.config)
    assert "Limite de 20 arquivos" in last


@pytest.mark.req("F17-RF-05")
async def test_sem_repositorio_e_token_recusado() -> None:
    no_repo = ToolContext("u", "c", None, cast(Any, None))
    config: RunnableConfig = {"configurable": {"ctx": no_repo}}
    assert await _call(buscar_no_repositorio, {"texto": "cpf"}, config) == NO_REPO

    s = Setup(token="github_pat_revogado_0000000000000")
    result = await _call(listar_arquivos_do_repositorio, {}, s.config)
    assert "recusou o token" in result
    assert s.invalidated == 1
