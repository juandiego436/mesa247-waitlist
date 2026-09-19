# Modelo de ramificación y entornos

## Antes de nada: por qué esto es GitFlow y qué me preocupa de esa elección

El Tech Lead pidió GitFlow y GitFlow es lo que hay aquí. Dejo escrito el reparo para que quede en el registro, no para discutirlo otra vez:

**GitFlow se diseñó para software con versiones y lanzamientos programados** — instaladores, SDKs, cosas donde conviven varias versiones en producción a la vez. Su propio autor publicó en 2020 una nota diciendo que si entregas una aplicación web de forma continua, probablemente no lo necesites. Aquí desplegamos a Cloud Run, hay **una sola versión viva** y el piloto dura tres semanas.

El coste concreto en este proyecto:

- `develop` y `main` divergen, y cada divergencia es una fusión que puede salir mal.
- Una corrección urgente un viernes a las nueve necesita `hotfix/` desde `main`, fusión a `main` **y** a `develop`. Son cuatro pasos de git con el restaurante esperando.
- Las ramas `release/` tienen sentido cuando hay una fase de estabilización. Con tres locales y despliegue continuo, no la hay.

**Lo que propondría en su lugar:** `main` siempre desplegable, ramas de trabajo cortas, y los entornos por *etiqueta de despliegue* y no por rama — el mismo commit sube a staging, se mira, y sube a producción. Menos fusiones, menos sitios donde el código puede quedarse atrás.

**Dicho eso, GitFlow tiene una ventaja real aquí:** el mapeo rama → entorno es obvio para cualquiera que entre al proyecto, y en un equipo donde alguien construye solo eso vale algo. Está montado, funciona y está documentado. Si alguien quiere cambiarlo más adelante, el cambio es barato.

## Las ramas

| Rama | Entorno | Perfil | Quién despliega |
|---|---|---|---|
| `main` | Producción | `prod` | Solo fusiones de `release/*` o `hotfix/*`, con etiqueta |
| `develop` | Desarrollo | `dev` | Automático en cada fusión |
| `release/x.y.z` | Staging | `staging` | Automático mientras la rama viva |
| `feature/*` | — | `local` | No se despliega. Sale de `develop` y vuelve a `develop` |
| `hotfix/*` | Producción | `prod` | Sale de `main`. **Vuelve a `main` y a `develop`** |

El perfil del backend (`MESA247_PROFILE`) y el modo del frontend (`--mode`) se eligen por entorno, no por rama: la rama decide *dónde* se despliega, la variable decide *cómo se comporta*. Son dos cosas distintas y mezclarlas es cómo alguien acaba desplegando a producción con la interactiva de FastAPI abierta.

## El flujo, en comandos

**Una funcionalidad nueva**

```bash
git switch develop && git pull
git switch -c feature/reordenar-la-cola
# ... trabajo, commits ...
git switch develop
git merge --no-ff feature/reordenar-la-cola
git branch -d feature/reordenar-la-cola
```

`--no-ff` siempre: el commit de fusión es lo que permite ver de un vistazo qué entró como una unidad. Sin él, el historial es una fila de commits sueltos y no se puede revertir una funcionalidad entera.

**Un lanzamiento**

```bash
git switch -c release/0.2.0 develop     # a partir de aquí, staging
# solo correcciones en esta rama, nada nuevo
git switch main && git merge --no-ff release/0.2.0
git tag -a v0.2.0 -m "..."
git switch develop && git merge --no-ff release/0.2.0   # ← el que se olvida
```

Esa última línea es la que se salta todo el mundo. Si se olvida, las correcciones hechas durante la estabilización **desaparecen en el siguiente lanzamiento** y el mismo error vuelve a producción. Es el fallo más común de GitFlow y por eso está escrito aquí.

**Una urgencia un viernes a las nueve**

```bash
git switch -c hotfix/mesas-no-se-liberan main
# ... el arreglo mínimo, nada más ...
git switch main && git merge --no-ff hotfix/mesas-no-se-liberan
git tag -a v0.2.1 -m "..."
git switch develop && git merge --no-ff hotfix/mesas-no-se-liberan
```

Mismo aviso: **las dos fusiones**. Y el arreglo mínimo, no el arreglo bonito — el bonito va a `develop` el lunes.

## Correspondencia con los perfiles

| | `local` | `dev` | `staging` | `prod` |
|---|---|---|---|---|
| Base de datos | SQLite | MySQL local | Cloud SQL | Cloud SQL |
| `/docs` de FastAPI | sí | sí | **no** | **no** |
| CORS | localhost | localhost | dominio staging | dominio prod |
| Token del anfitrión | de ejemplo | de ejemplo | **de Secret Manager** | **de Secret Manager** |
| Migraciones | `create_all` | Alembic | Alembic, job aparte | Alembic, job aparte |

El perfil **se niega a arrancar** si en `staging` o `prod` la interactiva sigue abierta, la base es SQLite, el token es el de ejemplo o CORS lleva comodín. Preferimos que el despliegue falle a que arranque mal: un contenedor que no levanta se ve en treinta segundos; una interactiva abierta en producción puede estar meses sin que nadie la note.

## Dónde falta trabajo

No hay CI configurado. Lo que pondría, en este orden:

1. En `feature/*` y en cada empuje: `pytest` y `tsc --noEmit`. Son cuatro segundos.
2. En `develop`: además, los tests de integración **contra MySQL**, no contra SQLite. El `SELECT ... FOR UPDATE` que protege del doble-booking **no se prueba de verdad en SQLite**, y ese es justo el fallo que no quiero descubrir en producción.
3. En `release/*` y `main`: construir la imagen, correr las migraciones como job, desplegar, y una comprobación de humo contra `/health/ready`.
4. Reglas de protección en `main` y `develop`: nada de empujar directo, revisión obligatoria.
