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
                source="claude",
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


def record_external_usage(
    db: Session,
    run_id: uuid.UUID,
    stage: str,
    source: str,
    units: int,
    estimated_cost_usd: float | None = None,
) -> None:
    """Same ledger as `record_usage`, for spend that isn't metered in Claude
    tokens -- Apify discovery runs and Firecrawl scrapes. `units` is a
    source-specific count (Apify: result rows returned; Firecrawl: scrape
    requests made, i.e. credits at its documented 1-credit-per-scrape rate).
    `estimated_cost_usd` is left `None` when a source's cost can't be
    inferred in dollars (Firecrawl credits vary in $ value by plan)."""
    try:
        db.add(
            UsageRecord(
                run_id=run_id,
                stage=stage,
                source=source,
                units=units,
                estimated_cost_usd=estimated_cost_usd,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("failed to record %s usage for run %s stage %s", source, run_id, stage)
