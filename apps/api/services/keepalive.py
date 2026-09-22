"""Self-ping loop to keep the free-tier Render web service from idling out.

Render's free tier spins a service down after ~15 minutes with no inbound
HTTP traffic and cold-starts it (30s+ delay) on the next request. Calling
the health-check function in-process doesn't count as that traffic -- Render
only resets the idle timer on requests that actually cross its public
ingress -- so this pings the service's own public URL over real HTTP, not
the local function.

`RENDER_EXTERNAL_URL` is set automatically by Render on every web service,
so this is a no-op anywhere else (local dev, tests, other hosts) without
needing any extra configuration.
"""

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

PING_INTERVAL_SECONDS = 10 * 60  # comfortably under Render's ~15 min idle timeout


async def keepalive_loop() -> None:
    base_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not base_url:
        return

    url = f"{base_url.rstrip('/')}/healthz"
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            await asyncio.sleep(PING_INTERVAL_SECONDS)
            try:
                resp = await client.get(url)
                logger.info("keepalive ping to %s -> %s", url, resp.status_code)
            except httpx.HTTPError:
                logger.warning("keepalive ping to %s failed", url, exc_info=True)
