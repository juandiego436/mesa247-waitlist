from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from waitlist.application.errors import ApplicationError
from waitlist.domain.errors import (
    DomainError,
    InvalidTransition,
    InvalidValue,
    TableDoesNotFit,
    TableNotAvailable,
)
from waitlist.infrastructure.config.settings import Settings, get_settings
from waitlist.infrastructure.http.routers import host, public

# El dominio no conoce HTTP a proposito. Esta tabla es el unico sitio donde se
# traduce, y esta aqui y no repartida por los routers para que se pueda leer de
# un vistazo que le llega al cliente cuando algo se rechaza.
_STATUS_POR_ERROR: list[tuple[type[Exception], int]] = [
    (InvalidValue, 422),
    (InvalidTransition, 409),   # el doble toque en la tablet
    (TableNotAvailable, 409),   # dos anfitriones, una mesa
    (TableDoesNotFit, 409),     # se resuelve reintentando con force=true
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(
        title=settings.api_title,
        version="0.1.0",
        # En staging y produccion esto es False y el perfil lo obliga: una
        # interactiva abierta es un mapa de la API para quien la encuentre.
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Host-Token"],
    )

    @app.exception_handler(DomainError)
    async def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
        for tipo, code in _STATUS_POR_ERROR:
            if isinstance(exc, tipo):
                return JSONResponse({"detail": str(exc)}, status_code=code)
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(ApplicationError)
    async def _app_error(_: Request, exc: ApplicationError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/health", tags=["operacion"])
    def health() -> dict:
        """Lo que mira Cloud Run para decidir si esta instancia sirve.

        No toca la base de datos a proposito: si MySQL parpadea, no queremos que
        Cloud Run mate y recree instancias sanas, que es como un incidente
        pequeno se convierte en uno grande.
        """
        return {"status": "ok", "profile": settings.profile.value}

    @app.get("/health/ready", tags=["operacion"])
    def ready() -> dict:
        """Esta si toca la base: es la que dice si podemos atender de verdad."""
        from sqlalchemy import text

        from waitlist.infrastructure.persistence.engine import get_engine

        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "profile": settings.profile.value}

    app.include_router(public.router)
    app.include_router(host.router)
    return app


app = create_app()
