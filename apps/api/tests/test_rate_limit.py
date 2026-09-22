import uuid
from datetime import datetime, timedelta, timezone

from apps.api.db.models import ObjectiveRejection
from apps.api.services.rate_limit import is_rate_limited, record_rejection

USER_ID = uuid.uuid4()


def test_not_rate_limited_with_no_rejections(db_session):
    assert is_rate_limited(db_session, USER_ID) is False


def test_rate_limited_after_max_attempts(db_session):
    for _ in range(3):
        record_rejection(db_session, USER_ID)

    assert is_rate_limited(db_session, USER_ID) is True


def test_not_rate_limited_below_max_attempts(db_session):
    record_rejection(db_session, USER_ID)
    record_rejection(db_session, USER_ID)

    assert is_rate_limited(db_session, USER_ID) is False


def test_old_rejections_outside_window_dont_count(db_session):
    old = ObjectiveRejection(
        supabase_user_id=USER_ID,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=45),
    )
    db_session.add(old)
    db_session.commit()
    record_rejection(db_session, USER_ID)
    record_rejection(db_session, USER_ID)

    # only 2 rejections are inside the 30-minute window -- the old one doesn't count
    assert is_rate_limited(db_session, USER_ID) is False


def test_rejections_are_scoped_per_user(db_session):
    other_user = uuid.uuid4()
    for _ in range(3):
        record_rejection(db_session, other_user)

    assert is_rate_limited(db_session, USER_ID) is False
    assert is_rate_limited(db_session, other_user) is True
