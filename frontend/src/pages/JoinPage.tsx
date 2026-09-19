import { useEffect, useState } from 'react'
import { ApiError, api, type Venue } from '../api/client'

/**
 * Pantalla 1 del prototipo: se abre al escanear el QR de la puerta.
 *
 * En produccion el QR ya lleva el venue_id en la URL; el desplegable solo existe
 * para poder probar los tres locales sin imprimir tres codigos.
 */
export function JoinPage({ onJoined }: { onJoined: (token: string) => void }) {
  const [venues, setVenues] = useState<Venue[]>([])
  const [venueId, setVenueId] = useState('')
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [partySize, setPartySize] = useState(2)
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    const fromUrl = new URLSearchParams(location.hash.split('?')[1] ?? '').get('venue')
    api
      .venues()
      .then((v) => {
        setVenues(v)
        setVenueId(fromUrl ?? v[0]?.venue_id ?? '')
      })
      .catch(() => setError('No pudimos cargar los locales'))
  }, [])

  const venue = venues.find((v) => v.venue_id === venueId)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSending(true)
    try {
      const place = await api.join(venueId, name, phone, partySize)
      onJoined(place.token)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Ya estaba en la cola: llevarlo a su puesto es la respuesta correcta,
        // no un error rojo. Toca 'Unirme' cinco veces porque esta nervioso.
        const token = (err.payload as { token?: string })?.token
        if (token) {
          onJoined(token)
          return
        }
      }
      setError(err instanceof Error ? err.message : 'Algo salio mal')
    } finally {
      setSending(false)
    }
  }

  return (
    <main className="card">
      <header className="card-head">
        <h1>{venue?.name ?? 'Lista de espera'}</h1>
        <p className="muted">Lista de espera · hoy</p>
      </header>

      <form onSubmit={submit}>
        {venues.length > 1 && (
          <label>
            Local
            <select value={venueId} onChange={(e) => setVenueId(e.target.value)}>
              {venues.map((v) => (
                <option key={v.venue_id} value={v.venue_id}>
                  {v.name}
                </option>
              ))}
            </select>
          </label>
        )}

        <label>
          Nombre
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Carla"
            required
            autoComplete="name"
          />
        </label>

        <label>
          Teléfono
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder={venue?.country === 'CL' ? '+56 9 8765 4321' : '+51 987 654 321'}
            required
            /* tel abre el teclado numérico en el móvil, que es donde se usa */
            type="tel"
            inputMode="tel"
            autoComplete="tel"
          />
        </label>

        <label>
          ¿Cuántos son?
          <div className="stepper">
            <button
              type="button"
              onClick={() => setPartySize((n) => Math.max(1, n - 1))}
              aria-label="Menos personas"
            >
              −
            </button>
            <output>{partySize}</output>
            <button
              type="button"
              onClick={() => setPartySize((n) => Math.min(20, n + 1))}
              aria-label="Más personas"
            >
              +
            </button>
          </div>
        </label>

        {error && <p className="error">{error}</p>}

        <button className="primary" disabled={sending || !venueId}>
          {sending ? 'Un momento...' : 'Unirme a la cola'}
        </button>
      </form>
    </main>
  )
}
