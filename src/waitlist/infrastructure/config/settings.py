from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Profile(str, Enum):
    """Un perfil por entorno. El perfil decide los VALORES POR DEFECTO; las
    variables de entorno siempre mandan por encima.

    Asi el despliegue en Cloud Run no necesita ningun fichero: lleva
    MESA247_PROFILE=prod y los secretos inyectados por Secret Manager.
    """

    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"

    @property
    def is_production_like(self) -> bool:
        return self in (Profile.STAGING, Profile.PROD)


def _active_profile() -> Profile:
    raw = os.getenv("MESA247_PROFILE", Profile.LOCAL.value).strip().lower()
    try:
        return Profile(raw)
    except ValueError as exc:
        opciones = ", ".join(p.value for p in Profile)
        raise RuntimeError(
            f"MESA247_PROFILE={raw!r} no existe. Perfiles validos: {opciones}"
        ) from exc


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MESA247_",
        env_file=(PROJECT_ROOT / f".env.{_active_profile().value}"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    profile: Profile = Field(default_factory=_active_profile)

    # --- base de datos ---
    database_url: str = "sqlite+pysqlite:///./waitlist.db"
    db_echo: bool = False
    db_pool_size: int = 5
    db_pool_recycle_seconds: int = 280  # por debajo del wait_timeout de Cloud SQL

    # --- api ---
    api_title: str = "Mesa247 · Lista de espera"
    docs_enabled: bool = True
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    # --- dominio ---
    hold_window_minutes: int = 10
    expected_turn_minutes: int = 75
    minutes_per_party: int = 8

    # --- seguridad ---
    # Token estatico por local para la tablet del anfitrion. En el piloto basta;
    # cuando haya que identificar a CADA anfitrion, esto se cambia por la sesion
    # de El Libro. Es una decision reversible y esta aislada en una dependencia.
    host_token: str = "anfitrion-local"

    notifier: str = "log"  # log | whatsapp

    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _guardas_de_produccion(self) -> "Settings":
        if not self.profile.is_production_like:
            return self
        # Una interactiva de FastAPI abierta en produccion es un mapa de la API
        # para cualquiera que la encuentre.
        if self.docs_enabled:
            raise RuntimeError(
                f"docs_enabled no puede estar activo con el perfil {self.profile.value}"
            )
        if self.database_url.startswith("sqlite"):
            raise RuntimeError(
                f"SQLite no vale para el perfil {self.profile.value}: usa MySQL"
            )
        if self.host_token == "anfitrion-local":
            raise RuntimeError(
                "MESA247_HOST_TOKEN sigue con el valor por defecto. Un token de "
                "ejemplo en produccion es una tablet que puede abrir cualquiera."
            )
        if "*" in self.cors_origins:
            raise RuntimeError("CORS con comodin no vale fuera de local")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
