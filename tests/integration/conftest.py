from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from waitlist.infrastructure.config import settings as settings_mod
from waitlist.infrastructure.persistence import engine as engine_mod
from waitlist.infrastructure.persistence import schema
from waitlist.infrastructure.http import dependencies as deps

HOST_TOKEN = "token-de-prueba"


@pytest.fixture
def client(tmp_path: Path):
    """Cada test con su propia base en disco y su propio cableado.

    En disco y no en memoria porque la unidad de trabajo abre una conexion por
    transaccion, y una SQLite en memoria muere con cada conexion.
    """
    os.environ.update(
        {
            "MESA247_PROFILE": "local",
            "MESA247_DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
            "MESA247_HOST_TOKEN": HOST_TOKEN,
            "MESA247_DOCS_ENABLED": "true",
        }
    )
    # Las tres caches que hay que soltar para que el perfil de prueba entre.
    settings_mod.get_settings.cache_clear()
    engine_mod.get_engine.cache_clear()
    deps._wiring.cache_clear()

    schema.metadata.create_all(engine_mod.get_engine())

    from waitlist.infrastructure.http.app import create_app

    with TestClient(create_app()) as c:
        yield c

    settings_mod.get_settings.cache_clear()
    engine_mod.get_engine.cache_clear()
    deps._wiring.cache_clear()


@pytest.fixture
def host_headers() -> dict[str, str]:
    return {"X-Host-Token": HOST_TOKEN}


@pytest.fixture
def venue(client) -> dict:
    """Siembra un local con mesas reales y devuelve sus ids."""
    from sqlalchemy import insert
    from uuid import uuid4

    engine = engine_mod.get_engine()
    venue_id = str(uuid4())
    mesas = {}
    with engine.begin() as conn:
        conn.execute(
            insert(schema.venues).values(
                id=venue_id,
                name="La Terraza Azul",
                timezone="America/Lima",
                country="PE",
                expected_turn_minutes=75,
            )
        )
        for label, seats in [("1", 2), ("2", 4), ("3", 6)]:
            tid = str(uuid4())
            mesas[label] = tid
            conn.execute(
                insert(schema.tables).values(
                    id=tid,
                    venue_id=venue_id,
                    label=label,
                    seats=seats,
                    status="available",
                    version=0,
                )
            )
    return {"id": venue_id, "tables": mesas}
