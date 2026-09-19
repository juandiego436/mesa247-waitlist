/**
 * Perfiles del frontend.
 *
 * Vite resuelve estas variables EN EL BUILD, no en tiempo de ejecucion: cada
 * entorno produce su propio paquete. Por eso `VITE_HOST_TOKEN` esta vacio en
 * staging y produccion -un token horneado dentro de un JavaScript publico no es
 * un secreto- y solo se rellena en desarrollo para no teclearlo todo el rato.
 */
export type Profile = 'development' | 'staging' | 'production'

export const config = {
  profile: (import.meta.env.VITE_PROFILE ?? 'development') as Profile,
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
  /** Solo se usa en desarrollo. En los demas perfiles lo teclea el anfitrion. */
  devHostToken: import.meta.env.VITE_HOST_TOKEN ?? '',
}

export const isProduction = config.profile === 'production'

/**
 * Cada cuanto vuelve a preguntar la pantalla del comensal.
 *
 * Son datos moviles y wifi malo: cinco segundos es suficiente para que la
 * posicion se sienta viva, y bastante mas barato que un WebSocket abierto en un
 * movil en la puerta de un restaurante. Cuando el WhatsApp entre, esto puede
 * subir a quince.
 */
export const GUEST_POLL_MS = 5000

/** La tablet esta enchufada y con wifi del local: puede permitirse mas ritmo. */
export const HOST_POLL_MS = 3000
