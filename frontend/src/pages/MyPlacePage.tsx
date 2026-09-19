import { useCallback, useEffect, useState } from 'react'
import { GUEST_POLL_MS } from '../config'
import { api, type GuestPlace } from '../api/client'

/**
 * Pantallas 2 y 3 del prototipo, fundidas en una.
 *
 * Durante el piloto ESTA pantalla es el canal de aviso: sin plantilla aprobada
 * por Meta no hay WhatsApp, asi que el comensal se entera aqui. El riesgo esta
 * aceptado y escrito en la nota: si cierra la pestana, no se entera.
 *
 * Por eso consulta cada cinco segundos y la respuesta es pequena: datos moviles
 * y wifi malo en la puerta.
 */
export function MyPlacePage({ token, onLeave }: { token: string; onLeave: () => void }) {
  const [place, setPlace] = useState<GuestPlace | null>(null)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      setPlace(await api.myPlace(token))
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sin conexión')
    }
  }, [token])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, GUEST_POLL_MS)
    // Cuando el movil vuelve del bloqueo, refrescar ya: pueden haber pasado
    // veinte minutos con la pantalla apagada.
    const onVisible = () => document.visibilityState === 'visible' && refresh()
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [refresh])

  if (!place) {
    return (
      <main className="card">
        <p className="muted">{error || 'Buscando tu puesto...'}</p>
      </main>
    )
  }

  if (place.status === 'called') {
    return (
      <main className="card ready">
        <header className="card-head">
          <h1>¡{place.guest_name.split(' ')[0]}, tu mesa está lista!</h1>
          <p className="muted">
            {place.venue_name}
            {place.table_label && ` · mesa ${place.table_label}`}
          </p>
        </header>
        <p className="big">Tienes 10 minutos para acercarte a la entrada</p>
        {place.on_the_way ? (
          <p className="confirmed">Nos avisaste que vas en camino</p>
        ) : (
          <button className="primary" onClick={() => api.onTheWay(token).then(refresh)}>
            Voy en camino
          </button>
        )}
        <button className="ghost" onClick={() => api.cancel(token).then(onLeave)}>
          Ya no voy
        </button>
      </main>
    )
  }

  if (place.status !== 'waiting') {
    const texto = {
      seated: 'Estás sentado. ¡Buen provecho!',
      cancelled: 'Saliste de la cola.',
      no_show: 'Te llamamos y no llegaste a tiempo.',
    }[place.status]
    return (
      <main className="card">
        <p className="big">{texto}</p>
        <button className="ghost" onClick={onLeave}>
          Volver
        </button>
      </main>
    )
  }

  return (
    <main className="card">
      <header className="card-head">
        <h1>{place.venue_name}</h1>
        <p className="muted">
          {place.guest_name} · {place.party_size} {place.party_size === 1 ? 'persona' : 'personas'}
        </p>
      </header>

      <p className="label">Estás en el puesto</p>
      {/* La animacion del prototipo se reduce a esto: la cifra cambia de color
          al avanzar. Es lo ultimo que mira alguien de pie en la puerta. */}
      <p className="position" key={place.position ?? 0}>
        {place.position}
      </p>

      <p className="label">Tiempo estimado</p>
      <p className="estimate">
        {place.estimated_wait_minutes === 0
          ? 'Ya casi'
          : `≈ ${place.estimated_wait_minutes} min`}
      </p>

      <p className="muted small">
        Deja esta pantalla abierta: te avisamos aquí cuando tu mesa esté lista.
      </p>
      {error && <p className="error small">{error}</p>}

      <button className="ghost" onClick={() => api.cancel(token).then(onLeave)}>
        Ya no voy
      </button>
    </main>
  )
}
