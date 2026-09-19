# Nota técnica — Lista de espera digital

**Piloto de tres locales · Mesa247**

---

## 1. Las tres preguntas al diseñador, y qué asumí

**1 · Si el sistema sabe qué mesas están ocupadas, ¿quién le dice cuándo se desocupan?**
Le falta una pantalla al prototipo y creo que no lo sabe. Sin ella, a las nueve de la noche las veinte mesas están marcadas como ocupadas, no hay ninguna que asignar y la tablet es un ladrillo.
**Asumo:** liberación explícita por el anfitrión **más** auto-liberación a los 75 minutos como red de seguridad. Un viernes con 40 personas en la puerta nadie toca "mesa libre" de forma fiable, así que el sistema tiene que recuperarse solo.

**2 · «Espera media»: ¿media o mediana?**
Un grupo que esperó dos horas mueve la media, y el gerente va a tomar decisiones mirando ese número.
**Asumo:** calculo las dos y muestro la media, que es lo que pide el prototipo. La mediana cuesta una línea y queda expuesta para cuando producto decida.

**3 · Sus números suman exacto: 97 + 31 + 14 = 142. ¿Qué pasa con los que siguen en cola al cierre?**
Esa suma asume que a la hora de cerrar no queda nadie esperando. En la vida real quedan. Si nadie los cierra, una entrada activa con la fecha de ayer es un fantasma que mañana aparece en la cola.
**Asumo:** un cubo `still_waiting` visible en el reporte, y cierre de jornada manual por el anfitrión. Esconder el número es peor que mostrarlo.

## 2. Qué construyo primero y qué corto

| Entra | Por qué | Est. |
|---|---|---|
| Unirse por QR sin login | Es el evento que hoy se pierde en el cuaderno | 35 min |
| Cola del anfitrión en la tablet | Sin esto no hay producto | 45 min |
| Llamar + asignar mesa real | Es el corazón del turno del anfitrión | 90 min |
| Cancelar (comensal y anfitrión) | El "se fue sin avisar" es el dolor declarado | 20 min |
| Pantalla de estado del comensal | Reemplaza al WhatsApp durante el piloto | 40 min |
| Reporte de cierre | Es lo que justifica pasar de 3 a 150 locales | 25 min |

| Sale | Por qué | Cuándo vuelve |
|---|---|---|
| **WhatsApp real** | Plantilla aprobada por Meta = días de trámite, no horas. Tarifa distinta por país. Y a veces la rechazan | Semana 2, con la plantilla ya aprobada |
| **Reporte por correo** | Necesita saber a qué hora cierra cada local, en dos husos, más un disparador programado. El cálculo —lo que tiene sustancia— ya está hecho | Semana 2, es un adaptador |
| **Arrastrar para reordenar** | Con asignación real por mesa, el anfitrión ya no llama "al siguiente": llama a quien entra en la mesa que se liberó. El orden pasa de regla a sugerencia | Puede que nunca. Se lo devuelvo al diseñador |
| **Animación de la posición** | Es lo último que mira alguien de pie en la puerta con datos móviles | Cuando sobre tiempo |
| **Etiqueta «Frecuente»** | Ese dato vive en El Libro. Es enriquecimiento de lectura, no un campo nuestro | Cuando se integre El Libro |

**Las estimaciones dependen de** que MySQL local ya esté levantado, que no haya que autenticar al anfitrión contra El Libro (asumo un token estático por local en el piloto) y de que el catálogo de mesas se siembre a mano para los tres locales.

## 3. Modelo de datos

    venue (id, external_ref→El Libro, nombre, timezone, country, expected_turn_min)
      │        timezone y country NO son opcionales: sin ellos ni la jornada
      │        ni los teléfonos se pueden calcular bien
      │
      ├── table (id, venue_id, external_ref, label, seats,
      │          status, held_by_entry_id, occupied_since, auto_release_at)
      │          UNIQUE parcial (held_by_entry_id) · UNIQUE (venue_id, label)
      │
      └── waitlist_entry
             id, venue_id, service_date, public_token UNIQUE
             guest_name, phone_e164, party_size
             status ∈ {waiting, called, seated, cancelled, no_show}
             joined_at, called_at, on_the_way_at, hold_expires_at
             closed_at, cancelled_by, call_count
             assigned_table_id, table_assigned_at, seated_over_capacity
             quoted_wait_minutes, version
             INDEX (venue_id, service_date, status, joined_at)  ← la cola

**Lo que deliberadamente no es una columna:** la posición en la cola (es una proyección de la cola entera; guardarla obliga a reescribir 40 filas cada vez que alguien se sienta, con dos anfitriones tocando la tablet a la vez) y el tiempo estimado (es función del ritmo del local, no de la entrada).

**Lo que sí es una columna aunque parezca redundante:** `quoted_wait_minutes`. Es lo que le prometimos al comensal al unirse, no se puede reconstruir después, y es lo único que permite comparar prometido contra real.

**El invariante que cruza dos tablas** —una mesa no puede estar retenida por dos comensales— se protege en tres capas: el servicio de dominio da el error legible, la transacción del caso de uso las guarda juntas o ninguna, y el índice único parcial en MySQL es la garantía real. Dos anfitriones tocando la misma mesa en el mismo segundo los separa el índice, no el dominio. Confundir esas tres capas es cómo se llega a un doble-booking en producción.

## 4. Lo que le devuelvo al diseñador, y cómo

Por el mismo hilo, el lunes, antes de escribir nada — no al final:

> «Tres cosas antes de arrancar. **Una:** si el sistema sabe qué mesas están ocupadas, necesito una pantalla para desocuparlas; si no, el viernes a las nueve no queda ninguna libre. **Dos:** el arrastrar-para-reordenar lo dejaría fuera del piloto, y no por tiempo: con asignación por mesa el anfitrión ya no llama al siguiente, llama a quien entra en la mesa que se liberó, y el orden deja de ser una regla. Prefiero verlo con los anfitriones una semana antes de construirlo. **Tres:** tus números del reporte suman exacto, o sea que asumiste que al cierre no queda nadie en cola. Quedan, y voy a mostrar ese número.»

El WhatsApp se lo diría distinto, porque ahí no hay negociación de diseño: la plantilla de Meta es un trámite de días y a veces la rechazan. Eso es una fecha, no una opinión.

## 5. Las decisiones que no se van a poder cambiar

1. **`service_date` explícito, calculado con la zona del local y con corte a las 5 a.m.** Un local que cierra a las 2 no cambia de jornada a medianoche, y el mismo instante UTC es el 11 en Lima y el 12 en Santiago. Si se guarda mal, el reporte de un local está mal para siempre y no hay forma de reconstruirlo.
2. **`public_token` opaco por entrada.** El comensal no tiene cuenta y el endpoint de "mi posición" es público. Si la URL llevara el id, cualquiera iterando ids se lleva 142 nombres y teléfonos. Cambiarlo después invalida los enlaces de todos los que estén en cola en ese momento.
3. **El catálogo de mesas es de solo lectura y El Libro es su dueño.** Si creamos mesas propias tenemos dos fuentes de verdad sobre el mismo objeto físico, y el día que El Libro siente una reserva en la mesa 7 hay dos grupos de pie delante de ella.
4. **`quoted_wait_minutes` se guarda al unirse.** Si no se captura en ese instante, ese dato no existe nunca.

**Riesgo conocido y aceptado para el piloto:** no detectamos choques con las reservas de El Libro. Con tres locales y el anfitrión mirando el salón, se absorbe. Con 150 no. Ahí hay que negociar un contrato con El Libro, y eso es semanas.

## 6. A producción

**Despliegue.** Cloud Run, que ya es el estándar de la casa, con imagen desde Cloud Build y Cloud SQL para MySQL por conector privado. `min-instances=1` durante el horario de servicio: un arranque en frío de tres segundos con alguien de pie en la puerta es un comensal perdido. Migraciones con Alembic en un job aparte, **nunca al arrancar el contenedor** — con varias instancias, dos migraciones concurrentes es cómo se corrompe un esquema. El front en Cloud Storage detrás de Cloud CDN.

**Qué vigilo.** Tres alarmas técnicas y una de producto:

- 5xx por encima del 1% en 5 minutos.
- p95 de la cola del anfitrión > 800 ms. Es la pantalla que se refresca sola en una tablet compartida; si se pone lenta, el anfitrión vuelve al cuaderno y ya no vuelve.
- Conexiones a Cloud SQL por encima del 80% del pool.
- **Cero altas en 30 minutos entre las 19:00 y las 22:00, hora local del local.** Esta es la que de verdad importa: todo puede estar en verde y el QR de la puerta estar despegado, rayado o apuntando a un dominio caído. El sistema técnicamente sano con cero altas un viernes es la falla que ninguna alarma de infraestructura ve.

**Cómo me entero un viernes a las 9 de la noche.** Las cuatro van a Opsgenie con escalado telefónico, no a un canal de Slack: un viernes a las nueve nadie mira Slack. La de producto entra como prioridad baja de lunes a jueves y alta viernes y sábado, que es cuando hay cola.

**Y el plan B no es técnico.** El anfitrión vuelve al cuaderno. Eso hay que decírselo **antes** del piloto, no durante la caída: una hoja impresa debajo de la tablet y una instrucción de una línea. Un sistema nuevo que se cae y deja al restaurante sin método es peor que no haberlo puesto.
