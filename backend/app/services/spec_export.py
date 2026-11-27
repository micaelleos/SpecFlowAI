"""Exportar as specs de um épico para o repositório, por PR (F18, ADR-011).

O conteúdo sai das specs guardadas nas ações do histórico (F10), com a mesma renderização do Jira
(`to_markdown`), sem LLM (F18-RT-03). Este módulo só prepara a ação proposta; a escrita acontece no
`ActionService`, depois do Confirm.
"""

import re
import unicodedata
from typing import Any, Protocol, runtime_checkable

from app.agent.spec.jira_payload import spec_of
from app.agent.spec.render import to_markdown
from app.agent.spec.schema import EpicSpec, WorkItemSpec
from app.agent.tools.context import PageDraft, RepoInfo, RepoReader, SpecExportError

MAX_TOTAL_BYTES = 200_000
MAX_STORIES = 30
MAX_BRANCH_TRIES = 20
SPEC_DIR = re.compile(r"^specs/(\d{3})-[^/]+$")


@runtime_checkable
class ExportStore(Protocol):
    def get_issue(self, uid: str, key: str) -> dict[str, Any] | None: ...
    def get_action(self, uid: str, action_id: str) -> dict[str, Any] | None: ...
    def child_actions(self, uid: str, epic_key: str) -> list[dict[str, Any]]: ...


class BranchProbe(Protocol):
    async def branch_sha(self, full_name: str, branch: str) -> str | None: ...


def slug(title: str, limit: int = 40) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    words = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    if len(words) > limit:  # corta numa palavra inteira
        cut = words[: limit + 1]
        words = cut[: cut.rfind("-")] if "-" in cut else words[:limit]
    return words.strip("-") or "epico"


def next_number(paths: set[str]) -> str:
    numbers = [int(m.group(1)) for p in paths if (m := SPEC_DIR.match(p))]
    return f"{max(numbers, default=0) + 1:03d}"


def _demote(markdown: str) -> str:
    """`## Seção` do Jira vira `#### Seção` dentro da história."""
    return re.sub(r"^## ", "#### ", markdown, flags=re.M)


def _criteria(spec: WorkItemSpec | EpicSpec) -> list[str]:
    return [c.id for c in spec.acceptance_criteria] if isinstance(spec, WorkItemSpec) else []


def render_files(
    folder: str,
    epic_key: str,
    epic: EpicSpec | WorkItemSpec,
    stories: list[tuple[str, WorkItemSpec | EpicSpec]],
    site_url: str,
) -> list[dict[str, str]]:
    """`spec.md` e `tasks.md` no formato Spec Kit (F18-RF-03)."""

    def link(key: str) -> str:
        return f"[{key}]({site_url}/browse/{key})"

    number = folder.split("/")[-1].split("-")[0]
    story_links = ", ".join(link(k) for k, _ in stories) or "—"
    spec = [
        f"# {number} — {epic.title}",
        "",
        "| Campo | Valor |",
        "|---|---|",
        "| **Status** | Rascunho |",
        f"| **Origem** | SpecFlow AI — épico {link(epic_key)} |",
        f"| **Histórias** | {story_links} |",
        "",
        "> [Spec](spec.md) · [Tarefas](tasks.md)",
        "",
        "## Parte A — Especificação",
        "",
        f"### Épico {epic_key}",
        "",
        _demote(to_markdown(epic)).rstrip(),
        "",
        "## Histórias",
    ]
    for key, story in stories:
        spec += ["", f"### {key} — {story.title}", "", _demote(to_markdown(story)).rstrip()]
    spec += ["", "## Rastreabilidade", "", "| História | Critérios de aceite |", "|---|---|"]
    spec += [f"| {link(k)} | {', '.join(_criteria(s)) or '—'} |" for k, s in stories]
    tasks = [
        f"# {number} — {epic.title} — Tarefas",
        "",
        "> [Spec](spec.md) · [Tarefas](tasks.md)",
        "",
    ]
    tasks += [
        f"- [ ] T{i:03d} [{key}] {story.title} — critérios: {', '.join(_criteria(story)) or '—'}"
        for i, (key, story) in enumerate(stories, start=1)
    ]
    return [
        {"path": f"{folder}/spec.md", "content": "\n".join(spec) + "\n"},
        {"path": f"{folder}/tasks.md", "content": "\n".join(tasks) + "\n"},
    ]


class RepoSpecExporter:
    """`SpecExporter` da conversa (F18): o histórico do usuário e o repositório vinculado."""

    def __init__(
        self,
        store: ExportStore,
        uid: str,
        repo: RepoReader,
        probe: BranchProbe,
        site_url: str,
    ) -> None:
        self._store = store
        self._uid = uid
        self._repo = repo
        self._probe = probe
        self._site_url = site_url

    def _spec(self, action_id: str | None) -> WorkItemSpec | EpicSpec | None:
        if not action_id:
            return None
        doc = self._store.get_action(self._uid, action_id)
        return spec_of((doc or {}).get("payload") or {})

    async def draft(self, epic_key: str) -> PageDraft:
        key = epic_key.strip().upper()
        record = self._store.get_issue(self._uid, key)
        epic = self._spec((record or {}).get("specActionId"))
        if epic is None or not isinstance(epic, EpicSpec):
            raise SpecExportError(
                f"{key} não é um épico criado pelo SpecFlow (só esses podem ser exportados)."
            )
        stories: list[tuple[str, WorkItemSpec | EpicSpec]] = []
        for action in sorted(
            self._store.child_actions(self._uid, key), key=lambda a: str(a.get("createdAt"))
        ):
            story_key = str((action.get("result") or {}).get("issue_key") or "")
            spec = spec_of(action.get("payload") or {})
            if story_key and spec is not None:
                stories.append((story_key, spec))
        if not stories:
            raise SpecExportError(f"O épico {key} não tem histórias criadas pelo SpecFlow.")
        stories = stories[:MAX_STORIES]
        info: RepoInfo = self._repo.info
        entries, _ = await self._repo.entries()
        folder = f"specs/{next_number({e.path for e in entries})}-{slug(epic.title)}"
        files = render_files(folder, key, epic, stories, self._site_url)
        if sum(len(f["content"].encode()) for f in files) > MAX_TOTAL_BYTES:
            raise SpecExportError("As specs passam de 200 KB; exporte um épico menor.")
        branch = await self._free_branch(info.full_name, f"specflow/{key.lower()}")
        title = f"docs(spec): {key} — {epic.title}"
        body = "\n".join(
            [
                f"Specs do épico [{key}]({self._site_url}/browse/{key}) geradas pelo SpecFlow AI.",
                "",
                *[f"- [{k}]({self._site_url}/browse/{k}) {s.title}" for k, s in stories],
            ]
        )
        keys = [key, *[k for k, _ in stories]]
        payload = {
            "repo": info.full_name,
            "base": info.default_branch,
            "branch": branch,
            "title": title,
            "body": body,
            "files": files,
            "epic_key": key,
            "issue_keys": keys,
        }
        preview = {
            "repo": info.full_name,
            "repo_url": info.url,
            "base": info.default_branch,
            "branch": branch,
            "title": title,
            "files": files,
            "epic_key": key,
            "issue_keys": keys,
        }
        return PageDraft("create_pull_request", payload, preview)

    async def _free_branch(self, full_name: str, base_name: str) -> str:
        for i in range(1, MAX_BRANCH_TRIES + 1):
            name = base_name if i == 1 else f"{base_name}-{i}"
            if await self._probe.branch_sha(full_name, name) is None:
                return name
        raise SpecExportError("Já há branches demais para este épico; apague as antigas.")
