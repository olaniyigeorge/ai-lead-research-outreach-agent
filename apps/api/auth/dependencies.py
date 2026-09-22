import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from apps.api.auth.allowlist import is_admin_email
from apps.api.auth.jwt import decode_supabase_jwt
from apps.api.auth.session import is_session_active
from apps.api.db.session import get_db


@dataclass
class AuthedActor:
    supabase_user_id: uuid.UUID
    email: str


def get_current_actor(request: Request, db: Session = Depends(get_db)) -> AuthedActor:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth_header.split(" ", 1)[1]

    payload = decode_supabase_jwt(token)

    sub = payload.get("sub")
    email = payload.get("email")
    if not sub or not email:
        raise HTTPException(status_code=401, detail="Token missing required claims")

    supabase_user_id = uuid.UUID(sub)

    if not is_session_active(db, supabase_user_id):
        raise HTTPException(status_code=401, detail="Session expired, please sign in again")

    return AuthedActor(supabase_user_id=supabase_user_id, email=email)


def get_current_admin_actor(
    actor: AuthedActor = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> AuthedActor:
    if not is_admin_email(db, actor.email):
        raise HTTPException(status_code=403, detail="Admin access required")
    return actor
