import { t, tServer } from './i18n'
import { APP_VERSION } from './version'

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''
const TOKEN_KEY = 'coffeepos-token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t: string | null) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY))

const BRANCH_KEY = 'coffeepos-branch'
const DEVICE_KEY = 'coffeepos-device'
export const getBranch = () => localStorage.getItem(BRANCH_KEY)
export const setBranch = (id: string | null) => (id ? localStorage.setItem(BRANCH_KEY, id) : localStorage.removeItem(BRANCH_KEY))
export const setDeviceToken = (token: string | null) => (token ? localStorage.setItem(DEVICE_KEY, token) : localStorage.removeItem(DEVICE_KEY))

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const token = getToken()
  const branch = getBranch()
  const device = localStorage.getItem(DEVICE_KEY)
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      method: init.method ?? (init.body === undefined ? 'GET' : 'POST'),
      headers: {
        ...(init.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(branch ? { 'X-Branch-Id': branch } : {}),
        ...(device ? { 'X-Device-Token': device } : {}),
        'X-App-Version': APP_VERSION,
      },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    })
  } catch {
    throw new ApiError(0, t("Server bilan aloqa yo'q. Internetni tekshiring"))
  }
  if (!res.ok) {
    let msg = t('Xato ({n})', { n: res.status })
    let detail: unknown
    try {
      const data = await res.json()
      detail = data.detail
      if (typeof data.detail === 'string') msg = tServer(data.detail)
      else if (data.detail && typeof data.detail.reason === 'string') msg = tServer(data.detail.reason)
      else if (Array.isArray(data.detail)) msg = t("Ma'lumotlar noto'g'ri to'ldirilgan")
    } catch {
      /* keep default message */
    }
    throw new ApiError(res.status, msg, detail)
  }
  return res.json() as Promise<T>
}

// Resolve generated receipt paths against the same API backend as authenticated calls.
export const publicApiUrl = (path: string) => new URL(`${BASE}${path}`, window.location.origin).href

export async function uploadImage(file: File): Promise<string> {
  if (file.size > 3 * 1024 * 1024) throw new Error(t('Rasm hajmi 3 MB dan oshmasin'))
  const token = getToken(), branch = getBranch(), device = localStorage.getItem(DEVICE_KEY)
  const res = await fetch(`${BASE}/api/images`, { method: 'POST', headers: {
    'Content-Type': file.type || 'application/octet-stream', 'X-App-Version': APP_VERSION,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(branch ? { 'X-Branch-Id': branch } : {}), ...(device ? { 'X-Device-Token': device } : {}),
  }, body: file })
  const data = await res.json()
  if (!res.ok) throw new Error(tServer(typeof data.detail === 'string' ? data.detail : 'Rasm yuklanmadi'))
  return data.url
}
