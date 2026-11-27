"""Conexão GitHub e vínculos no Firestore do emulador (F17-RT-01, F17-RT-04; T002)."""

import uuid
from datetime import UTC, datetime

import pytest
from google.cloud import firestore

from app.repositories.github import GitHubRepository


@pytest.mark.req("F17-RF-04")
@pytest.mark.req("F17-RT-04")
def test_desconectar_apaga_conexao_e_vinculos(db: firestore.Client) -> None:
    repo = GitHubRepository(db)
    uid = f"u-{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC)
    cid = repo.create_connection(
        uid, {"login": "po", "tokenCiphertext": b"cifrado", "status": "ok", "createdAt": now}
    )
    link = {"fullName": "po/loja", "url": "u", "defaultBranch": "main", "linkedAt": now}
    repo.set_link(uid, "ABC", link)
    repo.set_link(uid, "FIN", link)

    assert [c["login"] for c in repo.list_connections(uid)] == ["po"]
    assert repo.get_link(uid, "ABC") == link
    stored = list(db.collection("users").document(uid).collection("repo_links").stream())
    assert all(set(d.to_dict() or {}) == set(link) for d in stored)  # nada de código

    repo.delete_connection(uid, cid)

    assert repo.list_connections(uid) == []
    assert repo.get_link(uid, "ABC") is None
    assert repo.get_link(uid, "FIN") is None
