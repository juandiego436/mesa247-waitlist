import { useEffect, useState } from 'react'
import { JoinPage } from './pages/JoinPage'
import { MyPlacePage } from './pages/MyPlacePage'
import { HostBoardPage } from './pages/HostBoardPage'

/**
 * Enrutado propio, de veinte lineas, sin react-router.
 *
 * Son tres pantallas y dos de ellas las abre un comensal de pie en la puerta,
 * con datos moviles y wifi malo. Meter un router de 20 kB para elegir entre tres
 * vistas es peso que paga el comensal y no le devuelve nada. El dia que haya
 * rutas anidadas o carga diferida, se cambia: es una decision reversible.
 */
type Route = { name: 'join' } | { name: 'place'; token: string } | { name: 'host' }

function parse(hash: string): Route {
  const path = hash.replace(/^#\/?/, '').split('?')[0]
  if (path === 'host') return { name: 'host' }
  if (path.startsWith('q/')) return { name: 'place', token: path.slice(2) }
  return { name: 'join' }
}

export function App() {
  const [route, setRoute] = useState<Route>(() => parse(location.hash))

  useEffect(() => {
    const onHash = () => setRoute(parse(location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  // El token en la URL es lo que permite al comensal volver a su puesto si
  // cierra la pestana sin querer. Es su unica llave: no hay cuenta ni sesion.
  function goToPlace(token: string) {
    location.hash = `#/q/${token}`
  }

  switch (route.name) {
    case 'host':
      return <HostBoardPage />
    case 'place':
      return (
        <MyPlacePage token={route.token} onLeave={() => (location.hash = '#/')} />
      )
    default:
      return <JoinPage onJoined={goToPlace} />
  }
}
