import uuid
from datetime import datetime, timedelta, timezone

from apps.api.auth.session import is_session_active, start_session
from apps.api.db.models import AppSession

USER_ID = uuid.uuid4()


def test_fresh_session_is_active(db_session):
    start_session(db_session, USER_ID, "person@example.com")
    assert is_session_active(db_session, USER_ID) is True


def test_session_past_one_hour_is_not_active_even_if_structurally_valid(db_session):
    expired = AppSession(
        supabase_user_id=USER_ID,
        email="person@example.com",
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(expired)
    db_session.commit()

    assert is_session_active(db_session, USER_ID) is False


def test_unknown_user_has_no_active_session(db_session):
    assert is_session_active(db_session, uuid.uuid4()) is False
