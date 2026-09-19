# Lista de espera digital — Mesa247

Corte para el piloto de tres locales: **La Terraza Azul** y **Cuatro Vientos** (Lima) y
**Casa Mediterránea** (Santiago).

> **Estado actual: capa de dominio completa y testeada.** La persistencia, la API y el
> frontend todavía no están. Ver [Qué falta](#qué-falta) al final. La
> [nota técnica](docs/NOTA-TECNICA.md) tiene el corte completo, las estimaciones y el
> plan de producción.

## Levantarlo

No hace falta base de datos: el dominio no depende de ninguna.

```bash
python -m pip install -r requirements.txt
python -m pytest
```

    50 passed in 0.19s

`tzdata` **no es opcional**. `ServiceDate` depende de la zona horaria del local
(`America/Lima`, `America/Santiago`) y Windows no trae la base de datos de husos de IANA;
algunas imágenes slim de Linux tampoco. Fijarla en `requirements.txt` hace que la jornada
se calcule igual en el portátil de quien desarrolla y en Cloud Run.

## Arquitectura

Hexagonal, con un límite explícito: **cuatro puertos, no más.** Un puerto por cada cosa
"por si acaso" es sobre-ingeniería disfrazada de arquitectura.

    src/waitlist/
      domain/            cero imports de fuera. Se testea sin MySQL y sin FastAPI
        entities/        WaitlistEntry · Table
        value_objects/   PhoneNumber · ServiceDate · PublicToken · PartySize · GuestName
        services/        SeatingService (invariante entre agregados) · queue_view
        reports/         DailyReport (valor calculado, no entidad)
      application/
        ports/           WaitlistRepository · TableRepository · Clock · Notifier
        use_cases/
      infrastructure/
        persistence/     SQLAlchemy — único sitio con decoradores de base de datos
        http/
          routers/       public.py (comensal, sin login) · host.py (anfitrión)

### Tres decisiones que explican casi todo el código

**La posición en la cola no es un campo.** Depende de quién esté delante, o sea de la cola
entera. Guardarla obliga a reescribir 40 filas cada vez que alguien se sienta, con dos
anfitriones tocando la tablet a la vez. Se calcula al leer, en `queue_view.py`.

**Nada caduca solo: la caducidad se calcula al leer.** Ni la ventana de 10 minutos del
comensal ni la ocupación de la mesa disparan una transición automática. `hold_has_expired()`
y `effective_status()` son consultas. Eso nos ahorra un worker y un cron en Cloud Run, que
escala a cero y no tiene dónde alojar un proceso residente. Y deja la decisión donde debe
estar: el anfitrión es quien ve si la persona está en la puerta.

**El invariante de la mesa vive en tres capas y no hay que confundirlas.** Que una mesa no
pueda estar retenida por dos comensales lo protegen: el `SeatingService` (error legible,
tests rápidos), la transacción del caso de uso (se guardan juntas o ninguna) y un índice
único parcial en MySQL. **La garantía real bajo concurrencia es el índice.** Dos anfitriones
en dos tablets tocando la misma mesa en el mismo segundo los separa la base de datos, no el
dominio. Quien crea que el dominio le da atomicidad se lleva el doble-booking a producción.

### El público es público

`public.py` y `host.py` están separados desde el primer día, y no por orden estético. El
router público no tiene login, lo abre cualquiera que escanee el QR de la puerta y **nunca
devuelve el nombre ni el teléfono de otro comensal** — solo tu propia posición, y solo
contra tu `public_token` opaco. Mezclarlos en un router es cómo se filtran 142 teléfonos un
viernes.

## Máquina de estados

    WAITING ──call_for_table──▶ CALLED ──seat──▶ SEATED
       │  │                       │  │
       │  └────────seat───────────┘  ├──mark_no_show──▶ NO_SHOW
       │                             │
       └──cancel / remove────────────┴──cancel / remove──▶ CANCELLED

Los tres estados de la derecha son **terminales y definitivos**. El segundo toque en una
tablet con mal wifi muere ahí, con un `InvalidTransition` que el adaptador traduce a 409.

«Voy en camino» **no es un estado**: es una marca de tiempo sobre `CALLED`. No cambia lo que
el anfitrión puede hacer después, así que no merece las cuatro transiciones extra que un
estado propio arrastraría.

## Tests

50, en 0.19 s, sin base de datos. Cubren lo que se rompe un viernes, no lo que se ve:

| Archivo | Qué protege |
|---|---|
| `test_waitlist_entry.py` | La máquina de estados y el doble toque en la tablet |
| `test_seating.py` | Que una mesa no se dé a dos grupos; que se libere sola |
| `test_service_date.py` | Que la jornada no se rompa en Santiago ni a la 1 a.m. |
| `test_daily_report.py` | Los números exactos de la pantalla 5 del prototipo |
| `test_queue_view.py` | Que nadie "optimice" la posición metiéndola en una columna |
| `test_phone_number.py` | E.164 en PE, CL, EC y CO; que el móvil no se exponga |

## Qué falta

Este repositorio está en el paso 3 de un plan iterativo. Hecho:

- [x] Dominio: entidades, value objects, servicios, reporte
- [x] Tests del dominio

Pendiente, en este orden:

- [ ] Puertos y casos de uso
- [ ] Adaptador de persistencia (SQLAlchemy + MySQL) y migración con el índice único parcial
- [ ] API FastAPI: routers público y de anfitrión
- [ ] Frontend React + TypeScript: unirse, estado del comensal, cola del anfitrión
- [ ] Tests de integración sobre el invariante de la mesa (el que de verdad necesita base de datos)

Lo que **no** se va a construir en el piloto y por qué está en la
[nota técnica](docs/NOTA-TECNICA.md): WhatsApp real, reporte por correo, reordenar
arrastrando y la etiqueta «Frecuente».
