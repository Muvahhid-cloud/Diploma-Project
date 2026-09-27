from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.modules.auth.router import router as auth_router
from app.modules.health.router import router as health_router
from app.modules.projects.router import router as projects_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="BuildAI 3D API",
        version="0.1.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    register_error_handlers(app)

    app.include_router(health_router)
    v1 = APIRouter(prefix="/api/v1")
    v1.include_router(auth_router)
    v1.include_router(projects_router)
    app.include_router(v1)
    return app


app = create_app()
