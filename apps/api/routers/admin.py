import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.auth.allowlist import is_admin_email
from apps.api.auth.dependencies import AuthedActor, get_current_actor, get_current_admin_actor
from apps.api.db.session import get_db
from apps.api.schemas import (
    AccessRequestOut,
    AllowedActorOut,
    CreateAllowedActorBody,
    DecideAccessRequestBody,
    MeOut,
    OrgUsageEntryOut,
)
from apps.api.services.access_request_service import decide_access_request, list_pending_requests
from apps.api.services.admin_service import (
    create_allowed_actor,
    delete_allowed_actor,
    list_allowed_actors,
    org_usage_summary,
)

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
    return [
        AllowedActorOut(
            id=actor.id,
            email=actor.email,
            email_domain=actor.email_domain,
            label=actor.label,
            is_admin=actor.is_admin,
            expires_at=actor.expires_at,
            created_at=actor.created_at,
            last_login_at=last_login_at,
        )
        for actor, last_login_at in list_allowed_actors(db)
    ]


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


@router.get("/admin/access-requests", response_model=list[AccessRequestOut])
def list_access_requests_endpoint(
    _admin: AuthedActor = Depends(get_current_admin_actor),
    db: Session = Depends(get_db),
) -> list[AccessRequestOut]:
    return [AccessRequestOut.model_validate(r) for r in list_pending_requests(db)]


@router.post("/admin/access-requests/{request_id}/decide", response_model=AccessRequestOut)
def decide_access_request_endpoint(
    request_id: uuid.UUID,
    body: DecideAccessRequestBody,
    admin: AuthedActor = Depends(get_current_admin_actor),
    db: Session = Depends(get_db),
) -> AccessRequestOut:
    request = decide_access_request(db, request_id, body.decision, admin.email)
    return AccessRequestOut.model_validate(request)


@router.get("/admin/org-usage", response_model=list[OrgUsageEntryOut])
def list_org_usage_endpoint(
    _admin: AuthedActor = Depends(get_current_admin_actor),
    db: Session = Depends(get_db),
) -> list[OrgUsageEntryOut]:
    return [OrgUsageEntryOut(**entry) for entry in org_usage_summary(db)]
