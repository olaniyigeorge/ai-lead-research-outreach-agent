from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers import admin, auth, runs

app = FastAPI(title="Koya Lead Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
