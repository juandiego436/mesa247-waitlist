from __future__ import annotations

import logging

from waitlist.domain.entities.waitlist_entry import WaitlistEntry

logger = logging.getLogger("waitlist.notifier")


class LogNotifier:
    """El adaptador del piloto: registra y no manda nada.

    La plantilla de WhatsApp necesita aprobacion de Meta -dias de tramite, tarifa
    distinta por pais, y a veces la rechazan-, asi que durante el piloto el canal
    real es la pantalla del propio comensal, que consulta su puesto cada pocos
    segundos.

    El riesgo esta aceptado y escrito: si el comensal cierra la pestana, no se
    entera. Con tres locales y un anfitrion en la puerta, se absorbe.

    Este log no es decorativo: es la unica prueba de que el sistema decidio
    avisar. El dia que WhatsApp entre, sirve para comparar lo que quisimos
    mandar con lo que Meta acepto.
    """

    def table_is_ready(self, entry: WaitlistEntry, venue_name: str) -> None:
        logger.info(
            "AVISO mesa_lista entry=%s local=%s a=%s plantilla=%s",
            entry.id,
            venue_name,
            entry.phone.masked(),  # nunca el numero completo en los logs
            "mesa_lista_v1",
        )
