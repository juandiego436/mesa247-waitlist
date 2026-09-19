from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from waitlist.domain.entities.table import Table
from waitlist.domain.entities.waitlist_entry import WaitlistEntry
from waitlist.domain.errors import TableDoesNotFit
from waitlist.domain.value_objects.ids import TableId

# La ventana del prototipo: "Tienes 10 minutos para acercarte a la entrada".
DEFAULT_HOLD_WINDOW = timedelta(minutes=10)
# Cuanto dura una mesa ocupada antes de que el sistema la de por libre sola.
DEFAULT_EXPECTED_TURN = timedelta(minutes=75)


@dataclass(frozen=True)
class SeatingService:
    """Coordina entrada y mesa, que son dos agregados distintos.

    El invariante "una mesa no puede estar retenida por dos comensales" no cabe
    dentro de ninguna de las dos entidades: vive entre ellas. Se protege en tres
    capas, y conviene no confundirlas:

      1. aqui, que da el error legible y los tests rapidos;
      2. la transaccion del caso de uso, que las guarda juntas o ninguna;
      3. un indice unico parcial en MySQL sobre la mesa retenida.

    La garantia real bajo concurrencia es la (3). Dos anfitriones en dos tablets
    tocando la misma mesa en el mismo segundo los separa el indice, no esta
    clase. Quien crea que el dominio solo le da atomicidad se lleva el
    doble-booking a produccion.
    """

    hold_window: timedelta = DEFAULT_HOLD_WINDOW
    expected_turn: timedelta = DEFAULT_EXPECTED_TURN

    def call_for_table(
        self,
        entry: WaitlistEntry,
        table: Table,
        now: datetime,
        previous_table: Table | None = None,
        force: bool = False,
    ) -> None:
        # Validar antes de tocar nada: si la entrada no admite la transicion no
        # queremos haber retenido ya una mesa que luego hay que devolver.
        entry.ensure_active("llamar")

        over_capacity = not table.can_fit(entry.party_size)
        if over_capacity and not force:
            raise TableDoesNotFit(
                f"El grupo de {entry.party_size} no entra en la mesa "
                f"{table.label} ({table.seats} plazas)"
            )

        if previous_table is not None and previous_table.id != table.id:
            previous_table.release(now)

        table.hold_for(entry.id, now, self.hold_window)
        entry.call_for_table(
            table_id=table.id,
            now=now,
            hold_window=self.hold_window,
            over_capacity=over_capacity,
        )

    def seat(self, entry: WaitlistEntry, table: Table | None, now: datetime) -> None:
        entry.seat(now)
        if table is not None:
            table.occupy(now, self.expected_turn)

    def cancel_by_guest(
        self, entry: WaitlistEntry, table: Table | None, now: datetime
    ) -> TableId | None:
        entry.cancel_by_guest(now)
        return self._release(entry, table, now)

    def remove_by_host(
        self, entry: WaitlistEntry, table: Table | None, now: datetime
    ) -> TableId | None:
        entry.remove_by_host(now)
        return self._release(entry, table, now)

    def mark_no_show(
        self, entry: WaitlistEntry, table: Table | None, now: datetime
    ) -> TableId | None:
        entry.mark_no_show(now)
        return self._release(entry, table, now)

    @staticmethod
    def _release(
        entry: WaitlistEntry, table: Table | None, now: datetime
    ) -> TableId | None:
        table_id = entry.release_table()
        if table is not None and table_id is not None and table.id == table_id:
            table.release(now)
        return table_id
