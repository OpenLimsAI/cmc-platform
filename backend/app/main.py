from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import dispose_engine, init_engine
from .routers import signals, vicell


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()
    yield
    await dispose_engine()


app = FastAPI(title="CMC R&D USP Dashboard API", version="0.1.0", lifespan=lifespan)

origins = [o.strip() for o in settings.dev_extra_origins.split(",") if o.strip()]
if not origins:
    origins = ["http://localhost:3000", "http://localhost:5170"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals.router)
app.include_router(vicell.router)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
