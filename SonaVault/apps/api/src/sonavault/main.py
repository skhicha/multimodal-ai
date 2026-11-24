from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from sonavault.config import get_settings
from sonavault.slices.acoustics.router import router as acoustics_router
from sonavault.slices.admin.router import router as admin_router
from sonavault.slices.auth.router import router as auth_router
from sonavault.slices.documents.router import router as documents_router
from sonavault.slices.ingest.router import router as ingest_router
from sonavault.slices.jobs.router import router as jobs_router
from sonavault.slices.mfa.router import router as mfa_router
from sonavault.slices.search.router import router as search_router
from sonavault.slices.streams.router import router as streams_router
from sonavault.slices.transcripts.router import router as transcripts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="SonaVault API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )

    app.include_router(auth_router)
    app.include_router(mfa_router)
    app.include_router(admin_router)
    app.include_router(ingest_router)
    app.include_router(documents_router)
    app.include_router(streams_router)
    app.include_router(jobs_router)
    app.include_router(transcripts_router)
    app.include_router(acoustics_router)
    app.include_router(search_router)

    # Spec requires /metrics reachable only on the internal :9182 port, never
    # the public-facing port; production deploy binds a second uvicorn worker
    # for this app on 9182 behind the docker-bridge network only.
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    @app.get("/healthz", tags=["ops"])
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    async def readyz():
        return {"status": "ready"}

    return app


app = create_app()
