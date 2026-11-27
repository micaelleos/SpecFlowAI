"""GitHub só leitura (F17, ADR-010): conexão por token e vínculo projeto ↔ repositório."""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from app.api.deps import CurrentUser, GitHub
from app.services.github import (
    GitHubConnectionInput,
    GitHubConnectionOut,
    ProjectRepoOut,
    RepoLinkInput,
    RepoLinkOut,
    RepoOut,
)

router = APIRouter(tags=["github"])
ProjectKeyPath = Annotated[str, Path(pattern=r"^[A-Z][A-Z0-9_]{1,9}$")]


@router.get(
    "/api/v1/github/connections",
    response_model=list[GitHubConnectionOut],
    summary="Minha conexão com o GitHub (sem o token)",
)
async def list_connections(user: CurrentUser, service: GitHub) -> list[GitHubConnectionOut]:
    return await service.connections(user.uid)


@router.post(
    "/api/v1/github/connections",
    response_model=GitHubConnectionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Valida o token fine-grained no GitHub e guarda a conexão (token cifrado)",
    responses={
        409: {"description": "Já existe uma conexão"},
        422: {"description": "`github-invalid-token`: o GitHub recusou o token"},
        502: {"description": "GitHub inacessível"},
    },
)
async def connect(
    body: GitHubConnectionInput, user: CurrentUser, service: GitHub
) -> GitHubConnectionOut:
    return await service.connect(user.uid, body)


@router.post(
    "/api/v1/github/connections/{connection_id}/validate",
    response_model=GitHubConnectionOut,
    summary="Testa o token guardado; se o GitHub recusar, a conexão fica inválida",
)
async def validate(connection_id: str, user: CurrentUser, service: GitHub) -> GitHubConnectionOut:
    return await service.validate(user.uid, connection_id)


@router.delete(
    "/api/v1/github/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a conexão e todos os vínculos de repositório",
)
async def disconnect(connection_id: str, user: CurrentUser, service: GitHub) -> Response:
    await service.disconnect(user.uid, connection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/api/v1/github/repos",
    response_model=list[RepoOut],
    summary="Repositórios que o token vê (até 50), filtrados pelo nome",
    responses={409: {"description": "GitHub não conectado"}},
)
async def list_repos(
    user: CurrentUser,
    service: GitHub,
    q: Annotated[str, Query(max_length=100)] = "",
) -> list[RepoOut]:
    return await service.repos(user.uid, q)


@router.get(
    "/api/v1/jira/projects/{key}/repo",
    response_model=ProjectRepoOut,
    summary="Repositório vinculado ao projeto",
)
async def get_repo(key: ProjectKeyPath, user: CurrentUser, service: GitHub) -> ProjectRepoOut:
    return await service.project_repo(user.uid, key)


@router.put(
    "/api/v1/jira/projects/{key}/repo",
    response_model=RepoLinkOut,
    summary="Vincula o projeto a um repositório que o token vê (confere o acesso antes)",
    responses={
        404: {"description": "O token não vê o repositório"},
        409: {"description": "GitHub não conectado"},
    },
)
async def put_repo(
    key: ProjectKeyPath, body: RepoLinkInput, user: CurrentUser, service: GitHub
) -> RepoLinkOut:
    return await service.link(user.uid, key, body)


@router.delete(
    "/api/v1/jira/projects/{key}/repo",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desvincula o repositório (nada muda no GitHub)",
)
async def delete_repo(key: ProjectKeyPath, user: CurrentUser, service: GitHub) -> Response:
    await service.unlink(user.uid, key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
