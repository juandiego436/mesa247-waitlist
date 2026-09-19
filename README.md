# Lista de espera digital — Mesa247

Corte para el piloto de tres locales: **La Terraza Azul** y **Cuatro Vientos** (Lima) y **Casa Mediterránea** (Santiago).

Un comensal escanea el QR, entra en la cola y ve su puesto en vivo. El anfitrión ve la cola en la tablet, llama a alguien **para una mesa concreta**, lo sienta, y al cierre abre el reporte del día.

El corte completo, las estimaciones y lo que queda fuera están en la [nota técnica](docs/NOTA-TECNICA.md). El modelo de ramas y entornos, en [ramificación](docs/RAMIFICACION.md).

---

## Levantarlo en cinco minutos

Hacen falta Python 3.11+ y Node 20+. **No hace falta base de datos**: el perfil local usa SQLite.

```bash
python -m pip install -r requirements.txt
python -m alembic upgrade head
python scripts/seed.py
python -m uvicorn waitlist.infrastructure.http.app:app --app-dir src --port 8000
```

En otra terminal:

```bash
cd frontend && npm install && npm run dev
```

> `cd` y no `npm install --prefix frontend`: con `--prefix`, npm en Windows instala los paquetes pero **no enlaza `node_modules/.bin`**, así que el `tsc` del build no aparece y falla con un mensaje que no dice por qué. Comprobado clonando el repositorio desde cero.

| | |
|---|---|
| Comensal (QR) | http://localhost:5173 |
| Anfitrión (tablet) | http://localhost:5173/#/host |
| API | http://localhost:8000/docs |

El token del anfitrión en local es `anfitrion-local`; el frontend de desarrollo ya lo lleva.

### Los tests

```bash
python -m pytest
```

    75 passed in ~3s

`tzdata` **no es opcional**. `ServiceDate` depende de la zona horaria del local y Windows no trae la base de husos de IANA; algunas imágenes slim de Linux tampoco. Fijarla en `requirements.txt` hace que la jornada se calcule igual en el portátil y en Cloud Run.

## Perfiles

El perfil decide los **valores por defecto**; las variables de entorno siempre mandan por encima. Así el despliegue en Cloud Run no necesita ningún fichero: lleva `MESA247_PROFILE=prod` y los secretos inyectados por Secret Manager.

| | `local` | `dev` | `staging` | `prod` |
|---|---|---|---|---|
| Base de datos | SQLite | MySQL local | Cloud SQL | Cloud SQL |
| `/docs` | sí | sí | **no** | **no** |
| Token del anfitrión | de ejemplo | de ejemplo | Secret Manager | Secret Manager |
| Esquema | `create_all` | Alembic | Alembic, job aparte | Alembic, job aparte |

```bash
MESA247_PROFILE=dev python -m uvicorn ...     # backend
npm run build:staging --prefix frontend       # frontend
```

El perfil **se niega a arrancar** si en `staging` o `prod` la interactiva sigue abierta, la base es SQLite, el token es el de ejemplo o CORS lleva comodín. Preferimos que el despliegue falle a que arranque mal: un contenedor que no levanta se ve en treinta segundos; una interactiva abierta en producción puede estar meses sin que nadie la note.

## Arquitectura

Hexagonal, con un límite explícito: **cuatro puertos**. Un puerto por cada cosa "por si acaso" es sobre-ingeniería disfrazada de arquitectura.

    src/waitlist/
      domain/            cero imports de fuera. Se testea sin MySQL y sin FastAPI
        entities/        WaitlistEntry · Table
        value_objects/   PhoneNumber · ServiceDate · PublicToken · PartySize · GuestName
        services/        SeatingService (invariante entre agregados) · queue_view
        reports/         DailyReport (valor calculado, no entidad)
      application/
        ports/           WaitlistRepository · TableRepository · Clock · Notifier
        use_cases/       guest.py · host.py
      infrastructure/
        config/          perfiles y sus guardas
        persistence/     SQLAlchemy Core + mappers a mano (sin ORM en el dominio)
        http/
          routers/       public.py (comensal, sin login) · host.py (tablet)

Todo el cableado vive en un solo archivo, [`dependencies.py`](src/waitlist/infrastructure/http/dependencies.py). Cambiar SQLite por MySQL, o el notificador de log por WhatsApp, es una línea ahí y una variable de entorno. Si eso no se nota, la arquitectura no compró nada.

### Cuatro decisiones que explican casi todo el código

**La posición en la cola no es un campo.** Depende de quién esté delante, o sea de la cola entera. Guardarla obliga a reescribir 40 filas cada vez que alguien se sienta, con dos anfitriones tocando la tablet a la vez. Se calcula al leer.

**Nada caduca solo: la caducidad se calcula al leer.** Ni la ventana de 10 minutos del comensal ni la ocupación de la mesa disparan transiciones automáticas. `hold_has_expired()` y `effective_status()` son consultas. Eso ahorra un worker y un cron en Cloud Run —que escala a cero y no tiene dónde alojar un proceso residente— y deja la decisión donde debe estar: el anfitrión es quien ve si la persona está en la puerta.

**Llamar y asignar mesa son un solo acto**, porque en el salón real también lo son: se desocupa la 7, miras quién entra en la 7, la llamas. Y la liberación de la mesa es un **efecto** de las transiciones terminales, no algo que el caso de uso deba recordar.

**El invariante de la mesa vive en tres capas y no hay que confundirlas.** Que una mesa no pueda estar retenida por dos comensales lo protegen el `SeatingService` (error legible, tests rápidos), la transacción (se guardan las dos o ninguna) y un **`SELECT ... FOR UPDATE`** sobre la fila de la mesa. La garantía real bajo concurrencia es el bloqueo. **MySQL no tiene índices únicos parciales** —eso es Postgres—; el `UNIQUE (held_by_entry_id)` resuelve otra cosa, que una entrada no retenga dos mesas, y funciona porque MySQL admite varios `NULL` en un único. Y como **SQLite no implementa `FOR UPDATE`**, el test que de verdad prueba esto tiene que correr contra MySQL en CI.

### El público es público

`public.py` y `host.py` están separados desde el primer día, y no por orden estético. El router público no tiene login, lo abre cualquiera que escanee el QR de la puerta y **nunca devuelve el nombre ni el teléfono de otro comensal** — solo tu propia entrada, contra tu `public_token` opaco. Los teléfonos salen enmascarados incluso en la tablet del anfitrión, y en los logs.

## Máquina de estados

    WAITING ──call_for_table──▶ CALLED ──seat──▶ SEATED
       │  │                       │  │
       │  └────────seat───────────┘  ├──mark_no_show──▶ NO_SHOW
       │                             │
       └──cancel / remove────────────┴──cancel / remove──▶ CANCELLED

Los tres de la derecha son **terminales y definitivos**. El segundo toque en una tablet con mal wifi muere ahí, con un `InvalidTransition` que el adaptador traduce a 409.

«Voy en camino» **no es un estado**: es una marca de tiempo sobre `CALLED`. No cambia lo que el anfitrión puede hacer después, así que no merece las cuatro transiciones extra que un estado propio arrastraría.

## Tests

75, en unos 3 segundos. Cubren lo que se rompe un viernes, no lo que se ve.

| Archivo | Qué protege |
|---|---|
| `domain/test_waitlist_entry.py` | La máquina de estados y el doble toque en la tablet |
| `domain/test_seating.py` | Que una mesa no se dé a dos grupos; que se libere sola |
| `domain/test_service_date.py` | Que la jornada no se rompa en Santiago ni a la 1 a.m. |
| `domain/test_daily_report.py` | Los números exactos de la pantalla 5 del prototipo |
| `domain/test_queue_view.py` | Que nadie "optimice" la posición metiéndola en una columna |
| `domain/test_phone_number.py` | E.164 en PE, CL, EC y CO; que el móvil no se exponga |
| `domain/test_guest_name.py` | Que «Familia Rojas» y «Lucía y Ana» no se abrevien |
| `integration/test_end_to_end.py` | El cableado: transacción, códigos de estado, y que lo público siga siendo seguro al pasar por la API |

## Lo que no está

Cortado a propósito, con el porqué en la [nota técnica](docs/NOTA-TECNICA.md):

- **WhatsApp real.** Durante el piloto el canal de aviso es la propia pantalla del comensal. La plantilla de Meta son días de trámite y a veces la rechazan. El `Notifier` ya es un puerto: entra cambiando el adaptador.
- **Reporte por correo.** El cálculo está hecho y expuesto como endpoint; el envío necesita saber a qué hora cierra cada local en dos husos horarios.
- **Arrastrar para reordenar.** Con asignación real por mesa, el anfitrión ya no llama "al siguiente", y el orden deja de ser una regla. Se lo devolvemos al diseñador.
- **Etiqueta «Frecuente».** Ese dato vive en El Libro.
- **Integración con El Libro.** El catálogo de mesas se siembra a mano; `external_ref` queda preparado. **Riesgo conocido y aceptado: no detectamos choques con sus reservas.** Con tres locales se absorbe; con 150 no.
- **CI.** Está escrito qué pondría y en qué orden, en [ramificación](docs/RAMIFICACION.md).
