"""Conexão GitHub e vínculos projeto ↔ repositório (F17, ADR-010, Constituição II).

`users/{uid}/github_connections/{id}`: o token só cifrado. `users/{uid}/repo_links/{projectKey}`:
só o nome do repositório, o branch padrão e a URL; nenhum código é guardado (F17-RT-04).
"""

from typing import Any, cast

from google.cloud import firestore


class GitHubRepository:
    def __init__(self, db: firestore.Client) -> None:
        self._db = db

    def _user(self, uid: str) -> firestore.DocumentReference:
        return self._db.collection("users").document(uid)

    def _connections(self, uid: str) -> firestore.CollectionReference:
        return cast(firestore.CollectionReference, self._user(uid).collection("github_connections"))

    def _links(self, uid: str) -> firestore.CollectionReference:
        return cast(firestore.CollectionReference, self._user(uid).collection("repo_links"))

    def list_connections(self, uid: str) -> list[dict[str, Any]]:
        docs = self._connections(uid).order_by("createdAt").stream()
        return [{"id": d.id, **(d.to_dict() or {})} for d in docs]

    def create_connection(self, uid: str, data: dict[str, Any]) -> str:
        ref = self._connections(uid).document()
        ref.create(data)
        return str(ref.id)

    def update_connection(self, uid: str, connection_id: str, data: dict[str, Any]) -> None:
        self._connections(uid).document(connection_id).update(data)

    def delete_connection(self, uid: str, connection_id: str) -> None:
        """Remove a conexão e todos os vínculos (F17-RF-04), num lote."""
        batch = self._db.batch()
        for link in self._links(uid).stream():
            batch.delete(link.reference)
        batch.delete(self._connections(uid).document(connection_id))
        batch.commit()

    def get_link(self, uid: str, project_key: str) -> dict[str, Any] | None:
        snapshot = self._links(uid).document(project_key).get()
        return snapshot.to_dict() if snapshot.exists else None

    def set_link(self, uid: str, project_key: str, data: dict[str, Any]) -> None:
        self._links(uid).document(project_key).set(data)

    def delete_link(self, uid: str, project_key: str) -> None:
        self._links(uid).document(project_key).delete()
