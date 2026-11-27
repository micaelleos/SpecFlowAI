"""Histórico com um épico e duas histórias criados pelo SpecFlow (F18)."""

from typing import Any

from tests.chat_fakes import NOW, MemoryChatStore
from tests.spec_fixtures import payments_epic, pix_story

UID = "uid-alice"


def _action(aid: str, kind: str, payload: dict[str, Any], key: str, minute: int) -> dict[str, Any]:
    return {
        "id": aid,
        "kind": kind,
        "status": "done",
        "payload": payload,
        "result": {"issue_key": key, "url": f"https://exemplo.atlassian.net/browse/{key}"},
        "createdAt": NOW.replace(minute=minute),
        "conversationId": "c-0",
    }


def seed_epic(store: MemoryChatStore, stories: int = 2) -> None:
    epic = payments_epic().model_dump(mode="json")
    actions = store.actions.setdefault(UID, [])
    actions.append(
        _action("a-epic", "create_issue", {"project_key": "ABC", "spec": epic}, "ABC-10", 0)
    )
    store.issues.setdefault(UID, {})["ABC-10"] = {
        "specActionId": "a-epic",
        "issueType": "Epic",
        "summary": epic["title"],
        "createdAt": NOW,
    }
    titles = ["Pagar com Pix", "Pagar com boleto"][:stories]
    for i, title in enumerate(titles, start=1):
        spec = pix_story(title=title).model_dump(mode="json")
        payload = {"project_key": "ABC", "parent_key": "ABC-10", "spec": spec}
        actions.append(_action(f"a-s{i}", "create_issue", payload, f"ABC-{10 + i}", i))
    # Uma história de outro épico e uma proposta ainda pendente não entram.
    other = {
        "project_key": "ABC",
        "parent_key": "ABC-99",
        "spec": pix_story().model_dump(mode="json"),
    }
    actions.append(_action("a-other", "create_issue", other, "ABC-50", 9))
    pending = {**_action("a-pend", "create_issue", {**other, "parent_key": "ABC-10"}, "", 9)}
    pending["status"] = "pending"
    actions.append(pending)


class GitHubLinks:
    """`GitHubService` simulado: o projeto ABC ligado a `po/loja` (chat) e o cliente (Confirm)."""

    def __init__(self, linked: bool = True) -> None:
        from tests.github_fake import FakeGitHub

        self.github = FakeGitHub()
        self.has_link = linked
        self.invalid: list[dict[str, Any]] = []

    def _client(self) -> Any:
        import httpx

        from app.integrations.github.client import GitHubClient
        from tests.github_fake import VALID

        return GitHubClient(VALID, transport=httpx.MockTransport(self.github))

    async def linked(self, uid: str, project_key: str) -> Any:
        if not self.has_link or project_key != "ABC":
            return None
        link = {"fullName": "po/loja", "url": "https://github.com/po/loja", "defaultBranch": "main"}
        return self._client(), {"id": "gh-1"}, link

    async def client_for(self, uid: str) -> Any:
        return self._client(), {"id": "gh-1"}

    async def mark_invalid(self, uid: str, current: dict[str, Any]) -> None:
        self.invalid.append(current)


def jira_with_remote_links(status: int = 201) -> tuple[Any, list[dict[str, Any]]]:
    """Jira do chat, mais o `remotelink` da F18-RF-04 (registra os links pedidos)."""
    import json

    import httpx

    from tests.chat_fakes import jira_handler

    base, links = jira_handler(), []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/remotelink") and request.method == "POST":
            links.append({"path": request.url.path, **json.loads(request.content)})
            return httpx.Response(
                status, json={"id": 1} if status < 300 else {"errorMessages": ["x"]}
            )
        return base(request)

    return handler, links
