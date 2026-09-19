import { useCallback, useEffect, useState } from 'react'
import { HOST_POLL_MS, config } from '../config'
import {
  ApiError,
  api,
  hostApi,
  type Board,
  type DailyReport,
  type QueueItem,
  type Venue,
} from '../api/client'

/**
 * Pantalla 4 del prototipo: la cola en la tablet de la entrada.
 *
 * Diferencia deliberada con el prototipo: no se arrastra para reordenar. Con
 * asignacion real por mesa, el anfitrion ya no llama "al siguiente" sino a quien
 * entra en la mesa que se acaba de liberar, y el orden deja de ser una regla.
 * Esta explicado en la nota tecnica.
 */
export function HostBoardPage() {
  const [token, setToken] = useState(
    () => localStorage.getItem('host_token') ?? config.devHostToken,
  )
  const [venues, setVenues] = useState<Venue[]>([])
  const [venueId, setVenueId] = useState('')
  const [board, setBoard] = useState<Board | null>(null)
  const [report, setReport] = useState<DailyReport | null>(null)
  const [error, setError] = useState('')
  const [calling, setCalling] = useState<string | null>(null)

  useEffect(() => {
    api.venues().then((v) => {
      setVenues(v)
      setVenueId((current) => current || v[0]?.venue_id || '')
    })
  }, [])

  const refresh = useCallback(async () => {
    if (!venueId || !token) return
    try {
      setBoard(await hostApi.board(venueId, token))
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sin conexión')
      if (e instanceof ApiError && e.status === 401) setBoard(null)
    }
  }, [venueId, token])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, HOST_POLL_MS)
    return () => clearInterval(id)
  }, [refresh])

  async function run(action: () => Promise<unknown>) {
    try {
      await action()
      setError('')
    } catch (e) {
      // Un 409 aqui casi siempre es el segundo toque sobre algo ya resuelto, o
      // una mesa que otro anfitrion acaba de tomar. Se dice, no se esconde.
      setError(e instanceof Error ? e.message : 'Algo salió mal')
    } finally {
      await refresh()
    }
  }

  if (!token) {
    return (
      <main className="card">
        <h1>Tablet del anfitrión</h1>
        <label>
          Token del local
          <input
            onChange={(e) => {
              localStorage.setItem('host_token', e.target.value)
              setToken(e.target.value)
            }}
            placeholder="anfitrion-local"
          />
        </label>
      </main>
    )
  }

  const freeTables = board?.tables.filter((t) => t.status === 'available') ?? []

  return (
    <main className="board">
      <header className="board-head">
        <div>
          <h1>{board?.venue_name ?? '...'}</h1>
          <p className="muted">
            {board?.service_date} · {board?.in_queue ?? 0} en cola
            {board?.average_wait_minutes != null &&
              ` · espera media ${board.average_wait_minutes} min`}
          </p>
        </div>
        <div className="board-actions">
          {venues.length > 1 && (
            <select value={venueId} onChange={(e) => setVenueId(e.target.value)}>
              {venues.map((v) => (
                <option key={v.venue_id} value={v.venue_id}>
                  {v.name}
                </option>
              ))}
            </select>
          )}
          <button
            className="ghost"
            onClick={() =>
              report
                ? setReport(null)
                : hostApi.report(venueId, token).then(setReport)
            }
          >
            {report ? 'Ver la cola' : 'Cierre del día'}
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      {report ? (
        <ReportPanel report={report} />
      ) : (
        <div className="board-grid">
          <section>
            <h2>La cola</h2>
            {board?.queue.length === 0 && <p className="muted">Nadie esperando.</p>}
            {board?.queue.map((item) => (
              <QueueRow
                key={item.entry_id}
                item={item}
                calling={calling === item.entry_id}
                onToggleCall={() =>
                  setCalling(calling === item.entry_id ? null : item.entry_id)
                }
                onSeat={() => run(() => hostApi.seat(item.entry_id, token))}
                onNoShow={() => run(() => hostApi.noShow(item.entry_id, token))}
                onRemove={() => run(() => hostApi.remove(item.entry_id, token))}
                tables={freeTables}
                onPickTable={(tableId, force) =>
                  run(async () => {
                    await hostApi.call(item.entry_id, tableId, token, force)
                    setCalling(null)
                  })
                }
              />
            ))}
          </section>

          <section>
            <h2>Mesas</h2>
            <div className="tables">
              {board?.tables.map((t) => (
                <div key={t.table_id} className={`table-chip ${t.status}`}>
                  <strong>{t.label}</strong>
                  <span className="muted small">{t.seats} pers.</span>
                  {t.status !== 'available' && (
                    /* «Mesa libre»: la pantalla que le falta al prototipo.
                       Sin ella, a las nueve no queda ninguna que asignar. */
                    <button
                      className="tiny"
                      onClick={() => run(() => hostApi.releaseTable(t.table_id, token))}
                    >
                      Liberar
                    </button>
                  )}
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </main>
  )
}

function QueueRow({
  item,
  calling,
  onToggleCall,
  onPickTable,
  onSeat,
  onNoShow,
  onRemove,
  tables,
}: {
  item: QueueItem
  calling: boolean
  onToggleCall: () => void
  onPickTable: (tableId: string, force: boolean) => void
  onSeat: () => void
  onNoShow: () => void
  onRemove: () => void
  tables: { table_id: string; label: string; seats: number }[]
}) {
  const called = item.status === 'called'
  return (
    <article className={`row ${called ? 'called' : ''} ${item.hold_expired ? 'expired' : ''}`}>
      <span className="pos">{item.position}</span>
      <div className="who">
        <strong>{item.name}</strong>
        <span className="muted small">
          {item.party_size} pers. · {item.waited_minutes} min · {item.phone_masked}
        </span>
        {called && (
          <span className="badge">
            Mesa {item.table_label}
            {item.on_the_way && ' · va en camino'}
            {item.hold_expired && ' · se pasó el tiempo'}
          </span>
        )}
      </div>

      <div className="row-actions">
        {called ? (
          <>
            <button className="primary" onClick={onSeat}>
              Sentar
            </button>
            <button className="ghost" onClick={onNoShow}>
              No vino
            </button>
            <button className="ghost" onClick={onToggleCall}>
              Otra mesa
            </button>
          </>
        ) : (
          <>
            <button className="primary" onClick={onToggleCall}>
              Llamar
            </button>
            <button className="ghost" onClick={onRemove}>
              Quitar
            </button>
          </>
        )}
      </div>

      {calling && (
        <div className="picker">
          {tables.length === 0 && <span className="muted">No hay mesas libres.</span>}
          {tables.map((t) => {
            const cabe = t.seats >= item.party_size
            return (
              <button
                key={t.table_id}
                className={cabe ? 'tiny' : 'tiny warn'}
                /* Si no cabe, se avisa pero se permite: un anfitrion va a
                   sentar a 5 en una mesa de 4 y tiene razón al hacerlo. */
                onClick={() => onPickTable(t.table_id, !cabe)}
                title={cabe ? undefined : `Solo ${t.seats} plazas — forzar`}
              >
                {t.label} · {t.seats}
                {!cabe && ' ⚠'}
              </button>
            )
          })}
        </div>
      )}
    </article>
  )
}

function ReportPanel({ report }: { report: DailyReport }) {
  return (
    <section className="report">
      <h2>Cierre del día · {report.service_date}</h2>
      <dl>
        <Stat label="Se unieron" value={report.joined} />
        <Stat label="Se sentaron" value={report.seated} />
        <Stat label="Se fueron sin sentarse" value={report.left_without_seating} />
        <Stat label="No vinieron al ser llamados" value={report.no_show} />
        {/* Los numeros del prototipo suman exacto, o sea que asumen que al
            cierre no queda nadie. Quedan, y aqui se ven. */}
        <Stat label="Siguen en cola" value={report.still_waiting} />
        <Stat
          label="Espera media"
          value={report.average_wait_minutes == null ? '—' : `${report.average_wait_minutes} min`}
        />
        <Stat
          label="Espera mediana"
          value={report.median_wait_minutes == null ? '—' : `${report.median_wait_minutes} min`}
        />
        <Stat
          label="Prometido vs. real"
          value={
            report.quoted_vs_real_delta == null
              ? '—'
              : `${report.quoted_vs_real_delta > 0 ? '+' : ''}${report.quoted_vs_real_delta} min`
          }
        />
      </dl>
    </section>
  )
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}
