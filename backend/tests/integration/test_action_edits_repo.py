"""Versões da proposta editada no Firestore do emulador (F14-RT-01; T002)."""

import uuid
from datetime import timedelta

import pytest
from google.cloud import firestore

from app.agent.spec.jira_payload import create_payload, payload_hash
from app.agent.spec.schema import WorkItemSpec
from app.repositories.actions import ActionRepository
from app.services.action_edits import ActionEditService
from app.services.actions import ActionChangedError
from tests.chat_fakes import NOW
from tests.spec_fixtures import pix_story, pix_story_data


@pytest.mark.req("F14-RF-03")
@pytest.mark.req("F14-RT-01")
async def test_versao_nova_restaurar_e_conflito(db: firestore.Client) -> None:
    repo = ActionRepository(db)
    uid = f"u-{uuid.uuid4().hex[:8]}"
    payload = create_payload(pix_story(), "ABC", ["specflow"], None)
    aid = repo.create_action(
        uid,
        {
            "kind": "create_issue",
            "payload": payload,
            "payloadHash": payload_hash(payload),
            "preview": {"summary": pix_story().title, "project_key": "ABC"},
            "readiness": {},
            "labels": ["specflow"],
            "status": "pending",
            "conversationId": "c1",
            "createdAt": NOW,
            "expiresAt": NOW + timedelta(hours=24),
        },
    )
    service = ActionEditService(repo, clock=lambda: NOW)
    edited = WorkItemSpec.model_validate(pix_story_data(title="Login com SSO"))

    out = await service.save(uid, aid, edited, None, payload_hash(payload))
    stored = repo.get_action(uid, aid) or {}
    assert stored["version"] == 2
    assert stored["payload"]["spec"]["title"] == "Login com SSO"
    assert stored["payloadHash"] == out.payload_hash == payload_hash(stored["payload"])
    assert stored["agentVersion"]["payloadHash"] == payload_hash(payload)

    with pytest.raises(ActionChangedError):
        await service.save(uid, aid, pix_story(), None, payload_hash(payload))

    restored = await service.restore(uid, aid, out.payload_hash)
    assert restored.payload_hash == payload_hash(payload)
    assert (repo.get_action(uid, aid) or {})["editedBy"] == "agent"
