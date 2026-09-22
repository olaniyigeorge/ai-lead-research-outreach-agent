# Backend image for the FastAPI API. Milestone 0/1 has no separate worker
# process yet -- the Postgres job queue and its polling worker are a
# Milestone 2+ addition (architecture doc §6.4/§I.2) -- so this image runs
# only the API for now. render-entrypoint.sh is the single place to extend
# once that worker exists, since Render's free tier only offers Web
# Services, not Background Workers (both would need to share one container).
FROM python:3.12-slim

WORKDIR /app

# Node.js + the Claude Code CLI: claude_agent_sdk's query() shells out to
# the `claude` binary as a subprocess (apps/api/agent/options.py), so it
# must be on PATH in the image -- the Python package alone isn't enough.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y curl gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt ./apps/api/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt

COPY apps/__init__.py ./apps/__init__.py
COPY apps/api/__init__.py ./apps/api/__init__.py
COPY apps/api/agent ./apps/api/agent
COPY apps/api/auth ./apps/api/auth
COPY apps/api/db ./apps/api/db
COPY apps/api/integrations ./apps/api/integrations
COPY apps/api/routers ./apps/api/routers
COPY apps/api/services ./apps/api/services
COPY apps/api/config.py ./apps/api/config.py
COPY apps/api/main.py ./apps/api/main.py
COPY apps/api/schemas.py ./apps/api/schemas.py

# Claude Agent SDK skills. Each stage's ClaudeAgentOptions sets
# cwd=REPO_ROOT (apps/api/agent/options.py) and setting_sources=["project"],
# where REPO_ROOT resolves to this image's WORKDIR -- so the skill must live
# at .claude/skills relative to that same root, not inside apps/api.
COPY .claude/skills ./.claude/skills

COPY render-entrypoint.sh ./
RUN chmod +x render-entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

# Render (and most single-container hosts) override this with their own
# start command if configured to, but this default is what runs otherwise.
CMD ["./render-entrypoint.sh"]
