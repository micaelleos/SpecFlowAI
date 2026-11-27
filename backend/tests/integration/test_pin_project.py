"""Fixar o projeto da conversa no Firestore do emulador (F21-RT-01; T001)."""

import uuid

import pytest
from google.cloud import firestore

from app.repositories.conversations import ConversationRepository


@pytest.mark.req("F21-RF-03")
@pytest.mark.req("F21-RT-01")
def test_fixa_so_conversa_sem_projeto_e_nunca_sobrescreve(db: firestore.Client) -> None:
    repo = ConversationRepository(db)
    uid = f"u-{uuid.uuid4().hex[:8]}"
    free = repo.create_conversation(uid, {"title": "Nova", "projectKey": None})
    pinned = repo.create_conversation(uid, {"title": "Fixada", "projectKey": "SCRUM"})

    assert repo.pin_project(uid, free, "SCRUM") == "SCRUM"
    assert (repo.get_conversation(uid, free) or {})["projectKey"] == "SCRUM"
    assert repo.pin_project(uid, free, "VEND") == "SCRUM"  # a segunda não troca
    assert repo.pin_project(uid, pinned, "VEND") == "SCRUM"
    assert (repo.get_conversation(uid, pinned) or {})["projectKey"] == "SCRUM"
    assert repo.pin_project(uid, "nao-existe", "SCRUM") is None
