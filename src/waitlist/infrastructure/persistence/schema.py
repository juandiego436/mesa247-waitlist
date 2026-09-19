from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()

# Los UUID viajan como CHAR(36). Con 40 personas en cola por local, la
# diferencia contra BINARY(16) no se mide; la legibilidad al depurar un viernes
# por la noche si.
_ID = String(36)

venues = Table(
    "venues",
    metadata,
    Column("id", _ID, primary_key=True),
    Column("external_ref", String(64), nullable=True),  # id en El Libro
    Column("name", String(120), nullable=False),
    # Ninguna de estas dos es opcional: sin timezone no se puede calcular la
    # jornada, y sin country no se puede normalizar un telefono.
    Column("timezone", String(64), nullable=False),
    Column("country", String(2), nullable=False),
    Column("expected_turn_minutes", Integer, nullable=False, default=75),
)

tables = Table(
    "tables",
    metadata,
    Column("id", _ID, primary_key=True),
    Column("venue_id", _ID, ForeignKey("venues.id"), nullable=False),
    Column("external_ref", String(64), nullable=True),
    Column("label", String(32), nullable=False),
    Column("seats", Integer, nullable=False),
    Column("status", String(16), nullable=False, default="available"),
    Column("held_by_entry_id", _ID, nullable=True),
    Column("held_at", DateTime, nullable=True),
    Column("occupied_since", DateTime, nullable=True),
    Column("auto_release_at", DateTime, nullable=True),
    Column("version", Integer, nullable=False, default=0),
    UniqueConstraint("venue_id", "label", name="uq_table_label_por_local"),
    # Una entrada no puede retener dos mesas. Funciona porque MySQL admite
    # varios NULL en un indice unico, asi que las mesas libres no chocan.
    #
    # Lo que este indice NO hace es impedir que dos anfitriones retengan la
    # MISMA mesa: eso es una lectura-escritura perdida sobre una sola fila, y lo
    # resuelve el SELECT ... FOR UPDATE del repositorio. MySQL no tiene indices
    # unicos parciales; eso es Postgres.
    UniqueConstraint("held_by_entry_id", name="uq_una_mesa_por_entrada"),
)

waitlist_entries = Table(
    "waitlist_entries",
    metadata,
    Column("id", _ID, primary_key=True),
    Column("venue_id", _ID, ForeignKey("venues.id"), nullable=False),
    Column("service_date", Date, nullable=False),
    Column("public_token", String(64), nullable=False, unique=True),
    Column("guest_name", String(80), nullable=False),
    Column("phone_e164", String(20), nullable=False),
    Column("party_size", Integer, nullable=False),
    Column("status", String(16), nullable=False),
    Column("joined_at", DateTime, nullable=False),
    Column("called_at", DateTime, nullable=True),
    Column("on_the_way_at", DateTime, nullable=True),
    Column("hold_expires_at", DateTime, nullable=True),
    Column("call_count", Integer, nullable=False, default=0),
    Column("closed_at", DateTime, nullable=True),
    Column("cancelled_by", String(8), nullable=True),
    Column("assigned_table_id", _ID, nullable=True),
    Column("table_assigned_at", DateTime, nullable=True),
    Column("seated_over_capacity", Boolean, nullable=False, default=False),
    Column("quoted_wait_minutes", Integer, nullable=True),
    Column("version", Integer, nullable=False, default=0),
    # La consulta que la tablet del anfitrion ejecuta cada pocos segundos.
    Index("ix_cola_del_dia", "venue_id", "service_date", "status", "joined_at"),
)
