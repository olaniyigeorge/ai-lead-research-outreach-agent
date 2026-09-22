import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.auth.allowlist import is_admin_email
from apps.api.auth.dependencies import AuthedActor, get_current_actor, get_current_admin_actor
from apps.api.db.session import get_db
from apps.api.schemas import AllowedActorOut, CreateAllowedActorBody, MeOut
from apps.api.services.admin_service import create_allowed_actor, delete_allowed_actor, list_allowed_actors

router = APIRouter(tags=["admin"])


@router.get("/auth/me", response_model=MeOut)
def get_me(
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> MeOut:
    return MeOut(email=actor.email, is_admin=is_admin_email(db, actor.email))


@router.get("/admin/allowlist", response_model=list[AllowedActorOut])
def list_allowlist_endpoint(
    _admin: AuthedActor = Depends(get_current_admin_actor),
    db: Session = Depends(get_db),
) -> list[AllowedActorOut]:
    return [AllowedActorOut.model_validate(a) for a in list_allowed_actors(db)]


@router.post("/admin/allowlist", response_model=AllowedActorOut, status_code=201)
def create_allowlist_endpoint(
    body: CreateAllowedActorBody,
    _admin: AuthedActor = Depends(get_current_admin_actor),
    db: Session = Depends(get_db),
) -> AllowedActorOut:
    entry = create_allowed_actor(db, body.email, body.email_domain, body.label, body.expires_at)
    return AllowedActorOut.model_validate(entry)


@router.delete("/admin/allowlist/{entry_id}", status_code=204)
def delete_allowlist_endpoint(
    entry_id: uuid.UUID,
    _admin: AuthedActor = Depends(get_current_admin_actor),
    db: Session = Depends(get_db),
) -> None:
    delete_allowed_actor(db, entry_id)
