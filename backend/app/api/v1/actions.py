"""Confirmação humana das ações propostas (F06, ADR-003): a única porta de escrita no Jira.

Antes de confirmar, a pessoa pode editar a proposta (F14): a prévia é calculada sem gravar, e cada
"Save" grava uma versão nova; a confirmação confere o hash da versão exibida.
"""

from typing import Any

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from app.agent.spec.schema import AgentReadySpec
from app.agent.tools.jira_tools import Priority
from app.api.deps import ActionEdits, Actions, CurrentUser
from app.services.action_edits import ProposalPreview
from app.services.actions import ActionOut

router = APIRouter(prefix="/api/v1", tags=["actions"])

_PROBLEMS: dict[int | str, dict[str, Any]] = {
    404: {"description": "Ação inexistente ou de outro usuário"},
    409: {"description": "Já concluída, recusada ou em execução; `action` traz o estado"},
    410: {"description": "Expirada (24 h)"},
}
_EDIT_PROBLEMS: dict[int | str, dict[str, Any]] = {
    **_PROBLEMS,
    409: {
        "description": "`action-changed`: a proposta tem outra versão; `action-not-pending`: já "
        "tratada. `action` traz o estado atual"
    },
    422: {"description": "Spec inválida ou `action-not-editable` (tipo trocado, ação sem spec)"},
}

Hash = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class ConfirmIn(BaseModel):
    payload_hash: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        description="Hash da versão exibida (`ActionOut.payload_hash`); outro dá 409",
    )


class PreviewIn(BaseModel):
    spec: AgentReadySpec
    priority: Priority | None = None


class EditIn(PreviewIn):
    base_hash: str = Hash


class RestoreIn(BaseModel):
    base_hash: str = Hash


@router.post(
    "/actions/{action_id}/confirm",
    summary="Confirma e executa a ação exatamente como exibida",
    responses={
        **_PROBLEMS,
        409: {"description": "Já tratada ou `action-changed`; `action` traz o estado"},
        422: {"description": "O Jira não executou; `detail` traz o erro traduzido"},
        503: {"description": "Escritas no Jira desligadas"},
    },
)
async def confirm(
    action_id: str,
    user: CurrentUser,
    actions: Actions,
    body: ConfirmIn | None = Body(default=None),  # noqa: B008
) -> ActionOut:
    return await actions.confirm(
        user.uid, action_id, user.name, body.payload_hash if body else None
    )


@router.post(
    "/actions/{action_id}/reject",
    summary="Recusa a ação; nada é escrito no Jira",
    responses=_PROBLEMS,
)
async def reject(action_id: str, user: CurrentUser, actions: Actions) -> ActionOut:
    return await actions.reject(user.uid, action_id)


@router.post(
    "/actions/{action_id}/preview",
    summary="Prévia e prontidão da proposta editada, sem gravar (F14-RT-03)",
    responses=_EDIT_PROBLEMS,
)
async def preview(
    action_id: str, body: PreviewIn, user: CurrentUser, edits: ActionEdits
) -> ProposalPreview:
    return await edits.preview(user.uid, action_id, body.spec, body.priority)


@router.put(
    "/actions/{action_id}/spec",
    summary="Grava a edição como versão nova da proposta (F14-RT-01)",
    responses=_EDIT_PROBLEMS,
)
async def save_spec(
    action_id: str, body: EditIn, user: CurrentUser, edits: ActionEdits
) -> ActionOut:
    return await edits.save(user.uid, action_id, body.spec, body.priority, body.base_hash)


@router.post(
    "/actions/{action_id}/restore",
    summary="Volta a proposta à última versão do agente (F14-RF-03)",
    responses=_EDIT_PROBLEMS,
)
async def restore(
    action_id: str, body: RestoreIn, user: CurrentUser, edits: ActionEdits
) -> ActionOut:
    return await edits.restore(user.uid, action_id, body.base_hash)


@router.get(
    "/conversations/{conversation_id}/actions",
    summary="Ações propostas na conversa, para reidratar os cartões",
)
async def list_actions(
    conversation_id: str, user: CurrentUser, actions: Actions
) -> list[ActionOut]:
    return await actions.list(user.uid, conversation_id)
