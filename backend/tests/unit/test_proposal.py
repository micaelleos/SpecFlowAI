"""A proposta refeita a partir da spec (F14-RT-02, F14-RT-04): mesmas funções da ferramenta."""

from typing import Any

import pytest

from app.agent.spec.jira_payload import create_payload, payload_hash, update_payload
from app.agent.spec.proposal import ProposalEditError, editable_spec, revise
from app.agent.spec.schema import EpicSpec, WorkItemSpec
from tests.spec_fixtures import pix_story, pix_story_data


def _update_doc() -> dict[str, Any]:
    payload = update_payload("ABC-7", pix_story(), None, ["agent-ready", "specflow", "time-pix"])
    return {
        "kind": "update_issue",
        "payload": payload,
        "payloadHash": payload_hash(payload),
        "preview": {"issue_key": "ABC-7", "before": {"summary": "Antigo"}, "url": "u"},
    }


@pytest.mark.req("F14-RT-02")
def test_atualizacao_mantem_labels_de_fora_e_o_antes() -> None:
    spec = pix_story().model_copy(update={"objective": ""})
    version = revise(_update_doc(), spec)

    assert "time-pix" in version["labels"]
    assert "agent-ready" not in version["labels"]  # recalculada: a spec deixou de estar pronta
    assert version["preview"]["before"] == {"summary": "Antigo"}
    assert version["preview"]["issue_key"] == "ABC-7"
    assert version["payload"] == update_payload("ABC-7", spec, None, version["labels"])
    assert version["payloadHash"] == payload_hash(version["payload"])


@pytest.mark.req("F14-RT-02")
def test_criacao_mantem_projeto_pai_e_prioridade() -> None:
    payload = create_payload(pix_story(), "ABC", ["specflow"], "ABC-1", "Low")
    doc = {"kind": "create_issue", "payload": payload, "preview": {"project_name": "Loja"}}

    version = revise(doc, pix_story(title="Novo"))

    assert version["payload"]["parent_key"] == "ABC-1"
    assert version["payload"]["priority"] == "Low"
    assert version["preview"]["project_name"] == "Loja"
    assert version["preview"]["priority"] == "Low"


@pytest.mark.req("F14-RT-04")
def test_criterios_renumerados_e_tipo_fixo() -> None:
    data = pix_story_data()
    data["acceptance_criteria"] = list(reversed(data["acceptance_criteria"]))
    version = revise(_update_doc(), WorkItemSpec.model_validate(data))
    ids = [c["id"] for c in version["payload"]["spec"]["acceptance_criteria"]]
    assert ids == ["CA-01", "CA-02"]
    assert version["payload"]["spec"]["acceptance_criteria"][0]["title"] == "Provedor indisponível"

    with pytest.raises(ProposalEditError):
        revise(_update_doc(), EpicSpec.model_validate({"type": "epic", "title": "E"}))


@pytest.mark.req("F14-RF-06")
def test_so_propostas_com_spec_sao_editaveis() -> None:
    assert editable_spec(_update_doc()) is not None
    title_only = {"kind": "update_issue", "payload": {"issue_key": "ABC-7", "summary": "x"}}
    assert editable_spec(title_only) is None
    assert editable_spec({"kind": "create_page", "payload": {}}) is None
    with pytest.raises(ProposalEditError):
        revise(title_only, pix_story())
