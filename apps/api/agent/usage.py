"""Per-call Claude token/cost logging, so spend is reviewable per run and in
total (PRD requirement, architecture doc §C.3/§F.3). Best-effort: a logging
failure must never take down the agent call it was logging -- by the time
this runs, the call it's costing already succeeded.
"""

import logging
import uuid

from claude_agent_sdk import ResultMessage
from sqlalchemy.orm import Session

from apps.api.db.models import UsageRecord

logger = logging.getLogger(__name__)


def record_usage(db: Session, run_id: uuid.UUID, stage: str, result: ResultMessage) -> None:
    try:
        model_usage = result.model_usage or {}
        # A call typically hits one model; sum defensively in case of a
        # fallback-model retry within the same call.
        input_tokens = sum(m.get("inputTokens", 0) for m in model_usage.values()) or None
        output_tokens = sum(m.get("outputTokens", 0) for m in model_usage.values()) or None
        cache_read = sum(m.get("cacheReadInputTokens", 0) for m in model_usage.values()) or None
        cache_creation = sum(m.get("cacheCreationInputTokens", 0) for m in model_usage.values()) or None
        model = next(iter(model_usage.keys()), None)

        db.add(
            UsageRecord(
                run_id=run_id,
                stage=stage,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation,
                estimated_cost_usd=result.total_cost_usd,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("failed to record usage for run %s stage %s", run_id, stage)
