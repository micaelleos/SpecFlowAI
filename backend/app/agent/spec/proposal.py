"""Uma proposta de issue refeita a partir da spec (F14-RT-02).

A ferramenta do agente, a edição na tela e a revisão pelo agente usam as mesmas funções: o payload
sai de `create_payload`/`update_payload`, a prévia de `section_markdown`/`to_markdown` e a
prontidão de `evaluate`. Sem LLM e sem I/O.
"""

from typing import Any

from app.agent.spec.jira_payload import (
    ISSUE_TYPES,
    create_payload,
    payload_hash,
    spec_of,
    update_payload,
)
from app.agent.spec.readiness import LABEL_SPECFLOW, Readiness, evaluate, labels_for
from app.agent.spec.render import section_markdown, to_markdown
from app.agent.spec.schema import EpicSpec, WorkItemSpec

# Labels que o SpecFlow recalcula; as outras labels da issue ficam (F06-RF-06).
OWN_LABELS = {LABEL_SPECFLOW, "agent-ready", "human-only"}
EDITABLE_KINDS = ("create_issue", "update_issue")
# Campos da ação que formam uma versão da proposta (F14-RT-01).
VERSION_FIELDS = ("payload", "payloadHash", "preview", "readiness", "labels")


class ProposalEditError(ValueError):
    """A edição não cabe nesta proposta (tipo trocado, ação sem spec…)."""


def readiness_dict(readiness: Readiness) -> dict[str, Any]:
    return {
        "ready": readiness.ready,
        "config_version": readiness.config_version,
        "rules": [
            {
                "id": r.id,
                "label": r.label,
                "severity": r.severity.value,
                "passed": r.passed,
                "detail": r.detail,
            }
            for r in readiness.results
        ],
    }


def spec_preview(
    spec: WorkItemSpec | EpicSpec | None, readiness: Readiness | None, labels: list[str]
) -> dict[str, Any]:
    preview: dict[str, Any] = {"labels": labels}
    if spec is not None and readiness is not None:
        preview |= {
            "issue_type": ISSUE_TYPES[spec.type],
            "summary": spec.title,
            "markdown": to_markdown(spec),
            "sections": section_markdown(spec),
            "readiness": readiness_dict(readiness),
        }
    return preview


def editable_spec(doc: dict[str, Any]) -> WorkItemSpec | EpicSpec | None:
    """A spec da proposta, se ela é editável (criação ou atualização com spec; F14)."""
    if doc.get("kind") not in EDITABLE_KINDS:
        return None
    return spec_of(doc.get("payload") or {})


def _normalized(
    new: WorkItemSpec | EpicSpec, old: WorkItemSpec | EpicSpec
) -> WorkItemSpec | EpicSpec:
    """Mesmo tipo da proposta, critérios `CA-nn` renumerados e só as referências que já estavam
    nela (F14-RT-04; F19-RT-09: a edição não acrescenta links)."""
    if new.type != old.type:
        raise ProposalEditError(
            f"A proposta é de {ISSUE_TYPES[old.type]}; para trocar o tipo, peça ao agente."
        )
    update: dict[str, Any] = {}
    allowed = {r.url for r in old.references}
    kept = [r for r in new.references if r.url in allowed]
    if kept != new.references:
        update["references"] = kept
    if isinstance(new, WorkItemSpec):
        renumbered = [
            s.model_copy(update={"id": f"CA-{i:02d}"})
            for i, s in enumerate(new.acceptance_criteria, start=1)
        ]
        if renumbered != new.acceptance_criteria:
            update["acceptance_criteria"] = renumbered
    return new.model_copy(update=update) if update else new


def revise(
    doc: dict[str, Any], spec: WorkItemSpec | EpicSpec, priority: str | None = None
) -> dict[str, Any]:
    """A versão nova da proposta `doc` com a spec dada (campos de `VERSION_FIELDS`).

    Mantém o resto do que foi proposto: projeto, pai, issue, antes/depois e conflitos. `priority`
    `None` mantém a prioridade atual."""
    old = editable_spec(doc)
    if old is None:
        raise ProposalEditError("Esta proposta não tem uma spec para editar.")
    spec = _normalized(spec, old)
    payload: dict[str, Any] = doc["payload"]
    preview: dict[str, Any] = doc.get("preview") or {}
    readiness = evaluate(spec)
    priority = priority or payload.get("priority")
    if doc["kind"] == "create_issue":
        labels = sorted(labels_for(spec, readiness))
        new_payload = create_payload(
            spec, payload["project_key"], labels, payload.get("parent_key"), priority
        )
    else:
        others = [x for x in payload.get("labels") or [] if x not in OWN_LABELS]
        labels = sorted({*others, *labels_for(spec, readiness)})
        new_payload = update_payload(payload["issue_key"], spec, priority, labels)
    kept = {k: v for k, v in preview.items() if k not in ("labels", "priority")}
    new_preview = kept | spec_preview(spec, readiness, labels)
    if priority:
        new_preview["priority"] = priority
    return {
        "payload": new_payload,
        "payloadHash": payload_hash(new_payload),
        "preview": new_preview,
        "readiness": readiness_dict(readiness),
        "labels": labels,
    }
