import { config } from '../config'

export interface GuestPlace {
  token: string
  venue_name: string
  guest_name: string
  party_size: number
  status: 'waiting' | 'called' | 'seated' | 'cancelled' | 'no_show'
  position: number | null
  estimated_wait_minutes: number | null
  ahead: number
  joined_at: string
  table_label: string | null
  hold_expires_at: string | null
  on_the_way: boolean
}

export interface QueueItem {
  entry_id: string
  position: number
  name: string
  party_size: number
  waited_minutes: number
  estimated_wait_minutes: number
  status: GuestPlace['status']
  phone_masked: string
  table_label: string | null
  called_at: string | null
  hold_expired: boolean
  on_the_way: boolean
}

export interface TableInfo {
  table_id: string
  label: string
  seats: number
  status: 'available' | 'held' | 'occupied'
  held_by_entry_id: string | null
  free_at: string | null
}

export interface Board {
  venue_name: string
  service_date: string
  in_queue: number
  average_wait_minutes: number | null
  queue: QueueItem[]
  tables: TableInfo[]
}

export interface Venue {
  venue_id: string
  name: string
  timezone: string
  country: string
}

export interface DailyReport {
  service_date: string
  joined: number
  seated: number
  left_without_seating: number
  no_show: number
  still_waiting: number
  average_wait_minutes: number | null
  median_wait_minutes: number | null
  quoted_vs_real_delta: number | null
  adds_up: boolean
}

/**
 * Error de la API con su codigo, para que la pantalla pueda distinguir.
 *
 * El 409 no siempre es un fallo: cuando alguien ya esta en la cola, el backend
 * devuelve 409 CON su token, y lo correcto es llevarlo a su puesto en vez de
 * ensenarle un error rojo.
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public payload?: unknown,
  ) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(config.apiBaseUrl + path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    // Sin red. Pasa de verdad en la puerta de un restaurante.
    throw new ApiError(0, 'No hay conexion. Reintentando...')
  }

  if (response.status === 204) return undefined as T

  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : (detail?.message ?? 'Algo salio mal')
    throw new ApiError(response.status, message, detail)
  }
  return body as T
}

// --- comensal: sin cabeceras, sin sesion ---

export const api = {
  venues: () => request<Venue[]>('/api/public/venues'),

  join: (venue_id: string, name: string, phone: string, party_size: number) =>
    request<GuestPlace>('/api/public/queue', {
      method: 'POST',
      body: JSON.stringify({ venue_id, name, phone, party_size }),
    }),

  myPlace: (token: string) =>
    request<GuestPlace>(`/api/public/queue/${token}`),

  onTheWay: (token: string) =>
    request<void>(`/api/public/queue/${token}/on-the-way`, { method: 'POST' }),

  cancel: (token: string) =>
    request<void>(`/api/public/queue/${token}/cancel`, { method: 'POST' }),
}

// --- anfitrion: todo con el token de la tablet ---

function hostHeaders(token: string) {
  return { 'X-Host-Token': token }
}

export const hostApi = {
  board: (venueId: string, token: string) =>
    request<Board>(`/api/host/venues/${venueId}/board`, {
      headers: hostHeaders(token),
    }),

  call: (entryId: string, tableId: string, token: string, force = false) =>
    request<void>(`/api/host/entries/${entryId}/call`, {
      method: 'POST',
      headers: hostHeaders(token),
      body: JSON.stringify({ table_id: tableId, force }),
    }),

  seat: (entryId: string, token: string) =>
    request<void>(`/api/host/entries/${entryId}/seat`, {
      method: 'POST',
      headers: hostHeaders(token),
    }),

  noShow: (entryId: string, token: string) =>
    request<void>(`/api/host/entries/${entryId}/no-show`, {
      method: 'POST',
      headers: hostHeaders(token),
    }),

  remove: (entryId: string, token: string) =>
    request<void>(`/api/host/entries/${entryId}/remove`, {
      method: 'POST',
      headers: hostHeaders(token),
    }),

  releaseTable: (tableId: string, token: string) =>
    request<void>(`/api/host/tables/${tableId}/release`, {
      method: 'POST',
      headers: hostHeaders(token),
    }),

  report: (venueId: string, token: string) =>
    request<DailyReport>(`/api/host/venues/${venueId}/report`, {
      headers: hostHeaders(token),
    }),
}
