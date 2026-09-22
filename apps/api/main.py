import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.config import get_settings
from apps.api.routers import admin, auth, runs
from apps.api.services.keepalive import keepalive_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(keepalive_loop())
    yield
    task.cancel()


app = FastAPI(title="Koya Lead Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(runs.router)
app.include_router(admin.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}
