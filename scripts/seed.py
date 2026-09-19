"""Siembra los tres locales del piloto y sus mesas.

Los locales son de El Libro; aqui los sembramos a mano porque esa integracion
esta fuera del piloto. `external_ref` queda preparado para el dia que exista.

    python scripts/seed.py            # perfil activo (por defecto: local)
    MESA247_PROFILE=dev python scripts/seed.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import delete, insert  # noqa: E402

from waitlist.infrastructure.config.settings import get_settings  # noqa: E402
from waitlist.infrastructure.persistence import schema  # noqa: E402
from waitlist.infrastructure.persistence.engine import get_engine  # noqa: E402


def _id(*parts: str) -> str:
    """Ids deterministas: volver a sembrar no duplica ni cambia enlaces."""
    return str(uuid5(NAMESPACE_URL, "mesa247://" + "/".join(parts)))


LOCALES = [
    {
        "key": "terraza-azul",
        "name": "La Terraza Azul",
        "timezone": "America/Lima",
        "country": "PE",
        "expected_turn_minutes": 75,
        # Mezcla real de un salon: la mayoria de dos y cuatro.
        "mesas": [("1", 2), ("2", 2), ("3", 2), ("4", 4), ("5", 4),
                  ("6", 4), ("7", 4), ("8", 6), ("9", 6), ("10", 8)],
    },
    {
        "key": "cuatro-vientos",
        "name": "Cuatro Vientos",
        "timezone": "America/Lima",
        "country": "PE",
        "expected_turn_minutes": 60,
        "mesas": [("1", 2), ("2", 2), ("3", 4), ("4", 4), ("5", 6)],
    },
    {
        # El local de Santiago existe justamente para que el bug de husos
        # horarios salga en el portatil y no en produccion.
        "key": "casa-mediterranea",
        "name": "Casa Mediterranea",
        "timezone": "America/Santiago",
        "country": "CL",
        "expected_turn_minutes": 90,
        "mesas": [("T1", 2), ("T2", 2), ("T3", 4), ("T4", 4),
                  ("T5", 6), ("T6", 8)],
    },
]


def seed() -> None:
    settings = get_settings()
    engine = get_engine()
    if settings.is_sqlite:
        # Comodidad del perfil local. En los demas entornos el esquema es de
        # Alembic y solo de Alembic: dos duenos del esquema es como se llega a
        # una tabla que existe en dev y no en staging.
        schema.metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(delete(schema.waitlist_entries))
        conn.execute(delete(schema.tables))
        conn.execute(delete(schema.venues))

        for local in LOCALES:
            venue_id = _id("venue", local["key"])
            conn.execute(
                insert(schema.venues).values(
                    id=venue_id,
                    external_ref=None,
                    name=local["name"],
                    timezone=local["timezone"],
                    country=local["country"],
                    expected_turn_minutes=local["expected_turn_minutes"],
                )
            )
            for label, seats in local["mesas"]:
                conn.execute(
                    insert(schema.tables).values(
                        id=_id("table", local["key"], label),
                        venue_id=venue_id,
                        external_ref=None,
                        label=label,
                        seats=seats,
                        status="available",
                        version=0,
                    )
                )
            print(f"  {local['name']:22} {len(local['mesas']):2} mesas  {venue_id}")

    print(f"\nPerfil: {settings.profile.value}")
    print(f"Base:   {settings.database_url}")


if __name__ == "__main__":
    print("Sembrando los tres locales del piloto...\n")
    seed()
