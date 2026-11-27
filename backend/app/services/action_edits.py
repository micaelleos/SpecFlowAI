"""Edição da proposta antes da confirmação (F14, ADR-003, Constituição Art. IV).

Cada "Save" grava uma versão nova na própria ação, numa transação: payload, hash, prévia,
prontidão e labels saem das mesmas funções da ferramenta do agente (`agent/spec/proposal.py`).
A gravação só acontece se a pessoa editou a versão atual (`base_hash`); a confirmação confere o
hash que a tela mostra (`ActionService.confirm`), então o que vai ao Jira é sempre o que se viu.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from app.agent.spec.proposal import VERSION_FIELDS, ProposalEditError, editable_spec, revise
from app.agent.spec.schema import EpicSpec, WorkItemSpec
from app.core.errors import ApiProblemError
from app.core.logging import uid_hash
from app.core.telemetry import in_thread
from app.repositories.actions import Decide, TransitionConflictError
from app.services.actions import (
    ActionChangedError,
    ActionExpiredError,
    ActionNotFoundError,
    ActionNotPendingError,
    ActionOut,
    _expired,
    to_out,
)

log = logging.getLogger("app.actions")

EditedBy = Literal["agent", "user"]


class EditStore(Protocol):
    """O que a edição usa do `ActionRepository` (o chat passa o mesmo repositório)."""

    def get_action(self, uid: str, action_id: str) -> dict[str, Any] | None: ...
    def transition(self, uid: str, action_id: str, decide: Decide) -> dict[str, Any] | None: ...


class ProposalPreview(BaseModel):
    """O cartão como ficaria com a edição, sem gravar (F14-RT-03)."""

    preview: dict[str, Any]
    readiness: dict[str, Any]
    labels: list[str]


class ActionNotEditableError(ApiProblemError):
    def __init__(self, detail: str) -> None:
        super().__init__(422, "action-not-editable", "A proposta não aceita esta edição", detail)


Problem = tuple[str, str] | None


class ActionEditService:
    def __init__(
        self, store: EditStore, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._store = store
        self._clock = clock

    async def preview(
        self,
        uid: str,
        action_id: str,
        spec: WorkItemSpec | EpicSpec,
        priority: str | None = None,
    ) -> ProposalPreview:
        doc = await in_thread(self._store.get_action, uid, action_id)
        if doc is None:
            raise ActionNotFoundError()
        self._raise(self._editable(doc, None), doc)
        try:
            version = revise(doc, spec, priority)
        except ProposalEditError as exc:
            raise ActionNotEditableError(str(exc)) from None
        return ProposalPreview(
            preview=version["preview"], readiness=version["readiness"], labels=version["labels"]
        )

    async def save(
        self,
        uid: str,
        action_id: str,
        spec: WorkItemSpec | EpicSpec,
        priority: str | None,
        base_hash: str | None,
        by: EditedBy = "user",
    ) -> ActionOut:
        """Versão nova da proposta. `base_hash` `None` (só o agente): edita a versão atual."""
        now = self._clock()

        def change(doc: dict[str, Any]) -> dict[str, Any] | str:
            try:
                version = revise(doc, spec, priority)
            except ProposalEditError as exc:
                return str(exc)
            if version["payloadHash"] == doc.get("payloadHash"):
                return {}  # nada mudou: sem versão nova
            if by == "user":
                # A 1ª edição da pessoa guarda a versão do agente, para "Restore" (F14-RF-03).
                agent = doc.get("agentVersion") or {k: doc.get(k) for k in VERSION_FIELDS}
            else:
                agent = {k: version[k] for k in VERSION_FIELDS}
            return version | {"agentVersion": agent, "editedBy": by}

        return await self._version(uid, action_id, base_hash, now, change, by)

    async def restore(self, uid: str, action_id: str, base_hash: str) -> ActionOut:
        """Volta à última versão do agente (F14-RF-03)."""
        now = self._clock()

        def change(doc: dict[str, Any]) -> dict[str, Any] | str:
            agent = doc.get("agentVersion")
            if not agent:
                return "Esta proposta não foi editada."
            if doc.get("editedBy") != "user":
                return {}
            return {k: agent[k] for k in VERSION_FIELDS} | {"editedBy": "agent"}

        return await self._version(uid, action_id, base_hash, now, change, "user")

    async def _version(
        self,
        uid: str,
        action_id: str,
        base_hash: str | None,
        now: datetime,
        change: Callable[[dict[str, Any]], dict[str, Any] | str],
        by: EditedBy,
    ) -> ActionOut:
        problem: list[Problem] = [None]

        def decide(doc: dict[str, Any] | None) -> dict[str, Any] | None:
            problem[0] = None  # a transação pode repetir
            if doc is None:
                return None
            if found := self._editable(doc, base_hash, now):
                problem[0] = found
                return None
            result = change(doc)
            if isinstance(result, str):
                problem[0] = ("invalid", result)
                return None
            if not result:
                return None
            return result | {"version": int(doc.get("version") or 1) + 1, "editedAt": now}

        try:
            doc = await in_thread(self._store.transition, uid, action_id, decide)
        except TransitionConflictError:
            doc = await in_thread(self._store.get_action, uid, action_id)
            if doc is None:
                raise ActionNotFoundError() from None
            raise ActionChangedError(to_out(doc, self._clock())) from None
        if doc is None:
            raise ActionNotFoundError()
        self._raise(problem[0], doc)
        if doc.get("editedAt") == now:
            log.info(
                "action_edited",
                extra={
                    "fields": {
                        "event": "action_edited",
                        "uid_hash": uid_hash(uid),
                        "action_id": action_id,
                        "kind": doc["kind"],
                        "version": doc.get("version"),
                        "by": by,
                    }
                },
            )
        return to_out(doc, now)

    def _editable(
        self, doc: dict[str, Any], base_hash: str | None, now: datetime | None = None
    ) -> Problem:
        if _expired(doc, now or self._clock()):
            return ("expired", "")
        if doc["status"] != "pending":
            return ("not_pending", "")
        if editable_spec(doc) is None:
            return ("invalid", "Esta proposta não tem uma spec para editar.")
        if base_hash is not None and doc.get("payloadHash") != base_hash:
            return ("changed", "")
        return None

    def _raise(self, problem: Problem, doc: dict[str, Any]) -> None:
        if problem is None:
            return
        out = to_out(doc, self._clock())
        code, detail = problem
        if code == "expired":
            raise ActionExpiredError(out)
        if code == "not_pending":
            raise ActionNotPendingError(out)
        if code == "changed":
            raise ActionChangedError(out)
        raise ActionNotEditableError(detail)
