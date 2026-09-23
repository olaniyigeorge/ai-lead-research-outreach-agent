#!/bin/sh
# Render's free tier only offers Web Services, not Background Workers. This
# project doesn't have a worker process yet -- the Postgres job queue and
# its polling worker are a Milestone 2+ addition (architecture doc
# §6.4/§I.2). Once that worker exists, background it here exactly like:
#
#   python -m apps.api.worker.main &
#
# before the exec line below, so both processes share this one container
# and Render only ever sees one process bound to $PORT.
set -e

exec python -m uvicorn apps.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
