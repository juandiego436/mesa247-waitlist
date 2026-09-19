# Conversación con IA — Parte 1: la nota y el diseño del backend

**Asistente:** Claude (Claude Code) · **Sesión:** diseño del dominio, del 18 de septiembre

> **Sobre este archivo.** Es la transcripción de la sesión reconstruida desde el contexto
> de la propia sesión. Los turnos del usuario están literales. Las respuestas del asistente
> están completas salvo los bloques de código que son idénticos a archivos del repositorio,
> que se referencian en vez de repetirse (se indica dónde). **Recomiendo adjuntar además la
> exportación oficial del chat como versión canónica de este entregable.**

---

## Turno 1 — Usuario

> Vamos a desarrollar el backend para un sistema de 'Lista de espera digital'. Yo seré el
> Tech Lead y tú serás mi desarrollador par. El objetivo es construir un código mantenible,
> escalable y limpio.
>
> Reglas estrictas para nuestro flujo de trabajo:
>
> 1. Trabajaremos iterativamente. No intentes construir todo el sistema de golpe. Yo te
>    indicaré en qué capa o componente enfocarnos en cada paso.
> 2. Utilizaremos Arquitectura Hexagonal (Puertos y Adaptadores). El dominio debe estar
>    completamente aislado de frameworks externos, bases de datos o librerías HTTP.
> 3. El stack será: Python y FastAPI en el backend, React con TypeScript en el frontend, MySQL.
> 4. Antes de escribir código para un nuevo módulo, quiero que me propongas brevemente la
>    estructura de carpetas o el diseño de la entidad para que yo lo apruebe o corrija.
> 5. Si detectas una mala práctica en mis indicaciones, debes cuestionarla.
>
> Para empezar (Paso 1), analiza los requerimientos básicos de una lista de espera digital
> (un cliente se registra, se le asigna un tamaño de mesa, entra en cola, se le notifica
> cuando su mesa está lista, o puede cancelar). Basado en esto, propón únicamente la
> estructura de la Entidad de Dominio principal (`WaitlistEntry`) sin decoradores de base de
> datos. Solo propiedades y métodos de dominio. ¿Entendido?

*(Adjunto: el PDF del encargo.)*

## Turno 1 — Asistente

Leyó el PDF completo y abrió con tres objeciones antes de proponer nada:

**1. «Se le asigna un tamaño de mesa» no está en el encargo.** El prototipo pide *¿Cuántos
son?*, que es `party_size`, no una mesa asignada. Y asignar mesa **ya vive en El Libro** (el
sistema PHP que tiene los locales, sus mesas y sus reservas): meterlo en nuestro dominio
duplica la fuente de verdad de un sistema que no controlamos.

**2. «Se le notifica» no es un método del dominio.** La entidad decide *cuándo procede
llamar*; *cómo se entera el comensal* (WhatsApp con plantilla aprobada por Meta, SMS, o
polling) es un adaptador. Es la parte más frágil del encargo y no puede tocar el dominio.

**3. Hexagonal en una prueba de cuatro horas.** De acuerdo con aislar el dominio, pero con
un límite explícito: **tres puertos, no más.** Un puerto por cada cosa "por si acaso" se lee
como sobre-ingeniería, y el propio encargo penaliza construir de más.

Después propuso `WaitlistEntry` con: identidad (`id`, `venue_id`, `service_date`), datos del
comensal (`guest_name`, `phone`, `party_size`), estado y su historia (`status`, `joined_at`,
`called_at`, `on_the_way_at`, `hold_expires_at`, `call_count`, `closed_at`, `cancelled_by`),
`public_token` y `quoted_wait_minutes`. Y los métodos `join`, `call`, `confirm_on_the_way`,
`seat`, `cancel_by_guest`, `remove_by_host`, `mark_no_show`, más consultas puras.

**Lo que dejó fuera a propósito, con argumento:** `position` (es una proyección de la cola
entera; guardarla obliga a reescribir 40 filas por cada persona que se sienta),
`estimated_wait` (función del ritmo del local), `is_frequent` (vive en El Libro), la mesa y
el canal de notificación. Y `rank` para el reordenar-arrastrando: recomendó **cortarlo**,
porque añadirlo después es una migración trivial, o sea una decisión reversible que no hay
que pagar hoy.

**Dos decisiones marcadas como irreversibles:** `service_date` explícito calculado con la
zona del local (el mismo instante es el 11 en Lima y el 12 en Santiago), y `public_token`
opaco desde el principio (si la URL pública lleva el `id`, cualquiera iterando ids se lleva
142 nombres y teléfonos).

Cerró con tres preguntas: ¿`party_size` sin mesa o asignación real? ¿Corto el reordenar?
¿Añado `version` para bloqueo optimista? (recomendó que no).

---

## Turno 2 — Usuario

> 1. asignacion real

## Turno 2 — Asistente

Aceptó la corrección, pero nombró una bifurcación que "asignación real" no resolvía:

- **Lectura A — la mesa como dato.** Se registra en qué mesa quedó. Es un campo.
- **Lectura B — la mesa como recurso.** El sistema sabe qué mesas están libres, se llama al
  comensal *para una mesa concreta*, esa mesa queda retenida. Esto es gestión de salón.

Asumió B, y señaló la consecuencia que consideró **la decisión más difícil de deshacer de
todo el encargo**: si el sistema sabe qué mesas están ocupadas, alguien tiene que decirle
cuándo se desocupan. **Nadie lo pidió y el prototipo no tiene esa pantalla.** Sin eso, a las
nueve de la noche las veinte mesas están ocupadas y la tablet es un ladrillo.

Sobre la propiedad de la mesa: El Libro ya tiene las mesas y las reservas. Propuso catálogo
de **solo lectura** detrás de un puerto, ocupación por walk-in nuestra, y **los choques con
reservas de El Libro explícitamente fuera del piloto**, escrito como riesgo conocido.

Rediseñó la entidad: `call()` desaparece y se convierte en `call_for_table()`, porque en el
salón real asignar y llamar son un solo acto ("se desocupa la 7, miras quién entra en la 7,
la llamas"). Y la liberación de la mesa **no es un método que el caso de uso tenga que
acordarse de llamar**: es un efecto de las transiciones terminales.

Sobre sentar a 5 personas en una mesa de 4: **avisar, no impedir.** «Un anfitrión va a
hacerlo y tiene razón. Si el dominio lo bloquea, la tablet estorba y el cuaderno vuelve.»

Añadió la entidad `Table` y explicó que el invariante "una mesa no puede estar retenida por
dos comensales" **no cabe en ninguna de las dos entidades**: se protege en tres capas, y la
garantía real bajo concurrencia es un índice único parcial en MySQL, no el dominio.

**Cambió su propia recomendación anterior sobre el bloqueo optimista:** con mesas como
recurso sí hace falta un guardia, pero no es una columna `version` en la entrada —el
conflicto está en `Table`—, es el índice único.

Estimó **+2h 45min** sobre un presupuesto de 4 horas y avisó: *«acabamos de cambiar la
prueba de "lista de espera" a "mini gestor de salón" (…) si tu intención era demostrar
profundidad de dominio, funciona; si era entregar el corte que ellos pidieron, esto lo pone
en riesgo. Tú decides — es tu llamada y la ejecuto igual.»* Y preguntó qué sacrificar.

---

## Turno 3 — Usuario

> 1 Si recurso B
> 2 Reporte.

## Turno 3 — Asistente

Confirmó su lectura ("conservar el reporte, adelgazar la asignación") y pidió corrección si
era al revés. Definió qué significa "B flaca": se queda el recurso completo (retención,
liberación, conflicto imposible), se van las zonas, la sugerencia automática de mejor mesa,
el histórico por mesa y el puerto separado hacia El Libro.

**El hallazgo del turno:** la liberación automática no necesita scheduler. *«La
auto-liberación no se escribe, se calcula al leer.»* Una mesa cuyo `auto_release_at` ya pasó
se reporta como disponible cuando el anfitrión carga la pantalla. Lo mismo con la ventana de
10 minutos. Eso elimina **un worker, un cron y una fuente entera de bugs de reloj en Cloud
Run**, que escala a cero y no tiene dónde alojar un proceso residente.

Sobre el reporte: **no es una entidad.** Es un valor calculado, y sale casi gratis *porque*
`service_date` y `cancelled_by` ya estaban en la entidad. Cortó el **envío por correo**
(mismo problema del scheduler, más dos husos horarios) y dejó el reporte como endpoint.

Y encontró la tercera pregunta para el diseñador leyendo sus propios números: **97 + 31 + 14
= 142 suma exacto**, o sea que el diseñador asumió que al cierre no queda nadie en cola. En
la vida real quedan, y una entrada activa con la fecha de ayer es un fantasma en la cola de
mañana.

Propuso la estructura de carpetas, señaló que `public.py` y `host.py` van separados **por
superficie de ataque y no por orden estético**, y avisó de que la regla "sin decoradores de
ORM" tiene un precio concreto: hay que escribir mappers a mano (ofreció
`registry.map_imperatively()` como alternativa). Reconoció que ya iban **cuatro puertos y no
los tres prometidos**.

Presupuesto revisado: **~4h 20min**, por encima del límite, con lo que caería primero si se
alarga. Y una advertencia: sin WhatsApp, el canal de aviso es la pantalla del comensal; si
cierra la pestaña, no se entera. Riesgo aceptado y escrito.

---

## Turno 4 — Usuario

> Si inicia, crea una nueva carpeta y tambien inicia en el repository de mi cuenta en github
> juandiego436 generale el archivo md README y tambien la nota tecnica y las convesaciones
> de este chat y las diez linea.

## Turno 4 — Asistente

Escribió la capa de dominio completa. Dos cosas que descubrió ejecutando, no razonando:

**`tzdata` no es opcional.** Al probar `ZoneInfo('America/Lima')` en Windows falló:
`ZoneInfoNotFoundError`. Windows no trae la base de datos de husos de IANA, y algunas
imágenes slim de Linux tampoco. Pasó de ser un detalle a una dependencia fijada en
`requirements.txt`, porque `ServiceDate` depende de ella y el cálculo tiene que dar lo mismo
en el portátil y en Cloud Run.

**`masked()` filtraba un dígito de más en Ecuador.** El enmascarado usaba un corte de
posición fija que asumía longitud de 9 dígitos; con el prefijo `+593` dejaba ver un dígito
extra. Corregido a "código de país + tres últimos".

También corrigió que `SeatingService` estaba llamando a un método privado de la entidad
(`_require_active`) desde fuera, y lo hizo público.

Resultado: **50 tests en 0.19 segundos, sin base de datos.** Cubren la máquina de estados,
el invariante de la mesa (incluido "no se retiene mesa para alguien ya sentado", que valida
el orden de las operaciones), la jornada cruzando husos y la madrugada, y los números
exactos de la pantalla 5 del prototipo.

Sobre las diez líneas se negó a inventarlas: *«Si yo invento un proyecto, te toca defenderlo
tú en esa sala.»* Entregó el andamio con las preguntas y se ofreció a escribirlo sobre un
proyecto real.

---

## Lo que se rechazó o se recortó a lo largo de la sesión

| Propuesto | Decisión | Argumento |
|---|---|---|
| Columna `position` en la entrada | **No** | Es una proyección; 40 UPDATE por cada persona que se sienta |
| Columna `estimated_wait` | **No** | Función del ritmo del local, no de la entrada |
| `rank` para reordenar arrastrando | **Cortado** | Reversible: añadirlo después es un backfill trivial |
| Estado propio para «Voy en camino» | **No** | Es una marca de tiempo; un estado arrastra 4 transiciones |
| Columna `version` (bloqueo optimista) | **No** | El conflicto está en `Table`; lo resuelve un índice único |
| Scheduler para caducar retenciones | **No** | Se calcula al leer; ahorra worker + cron en Cloud Run |
| Puerto separado para el catálogo de El Libro | **Recortado** | El repositorio *es* el puerto; el adaptador llega después |
| Bloquear al sentar sobre capacidad | **No** | Avisar, no impedir. Si estorba, vuelve el cuaderno |
| WhatsApp real en el piloto | **Cortado** | Plantilla de Meta = días de trámite, y a veces la rechazan |
| Reporte por correo | **Cortado** | Scheduler otra vez, más dos husos. El cálculo ya está |
| `quoted_wait_minutes` | **Sí, se guarda** | Es la excepción: no se puede reconstruir después |
