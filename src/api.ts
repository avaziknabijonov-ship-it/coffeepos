import { Capacitor } from '@capacitor/core'
import { t, tServer } from './i18n'

const ENV_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.trim().replace(/\/$/, '') ?? ''
const SERVER_KEY = 'coffeepos-server-url'
const TOKEN_KEY = 'coffeepos-token'

export const isNativeApp = () => Capacitor.isNativePlatform()
export const getServerUrl = () => localStorage.getItem(SERVER_KEY) || ENV_BASE

// HTTP is supported only on a private local network for testing.
// A publicly accessible server must use HTTPS to protect staff PINs and tokens.
export function normalizeServerUrl(input: string): string {
  let url: URL
  try {
    url = new URL(input.trim())
  } catch {
    throw new Error(t('Server manzilini to‘g‘ri kiriting. Masalan: http://192.168.1.26:8000'))
  }
  const host = url.hostname
  const privateHost = host === 'localhost' || host === '127.0.0.1' || host.endsWith('.local')
    || /^192\.168\.\d{1,3}\.\d{1,3}$/.test(host)
    || /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(host)
    || /^172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}$/.test(host)
  if (!['http:', 'https:'].includes(url.protocol) || (url.protocol === 'http:' && (import.meta.env.VITE_STORE_BUILD === '1' || !privateHost))
    || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error(t('Server manzili xato. Internetdagi server uchun HTTPS ishlating.'))
  }
  return url.origin
}

async function fetchWithTimeout(url: string, options: RequestInit, timeout: number) {
  // AbortSignal.timeout is unavailable on older supported iPhones/iPads.
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    return await fetch(url, { ...options, signal: controller.signal })
  } finally { clearTimeout(timer) }
}

export async function checkServerUrl(input: string): Promise<string> {
  const base = normalizeServerUrl(input)
  let response: Response
  try {
    response = await fetchWithTimeout(`${base}/healthz`, { cache: 'no-store' }, 15_000)
  } catch {
    throw new Error(t('Serverga ulanib bo‘lmadi. Telefon va server tarmog‘ini tekshiring.'))
  }
  if (!response.ok) throw new Error(t('Bu manzilda CoffeePOS serveri topilmadi.'))
  try {
    const body: unknown = await response.json()
    if (typeof body === 'object' && body !== null && 'ok' in body && body.ok === true) return base
  } catch {
    // An HTML page or another service is not the CoffeePOS API.
  }
  throw new Error(t('Bu manzilda CoffeePOS serveri topilmadi.'))
}

export function saveServerUrl(base: string) {
  // Tokens belong to one server. Never reuse them on a different backend.
  const normalized = normalizeServerUrl(base)
  if (localStorage.getItem(SERVER_KEY) !== normalized) {
    localStorage.removeItem(TOKEN_KEY)
  }
  localStorage.setItem(SERVER_KEY, normalized)
}

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (token: string | null) => (token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY))

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, init: { method?: string; body?: unknown; authToken?: string | null } = {}): Promise<T> {
  // Browsers keep the existing /api Vite/nginx proxy. Android must use an absolute API URL.
  const base = isNativeApp() ? getServerUrl() : ENV_BASE
  if (isNativeApp() && !base) {
    throw new ApiError(0, t('Avval Server sozlamalarida manzilni kiriting.'))
  }

  if (isNativeApp() && base) normalizeServerUrl(base)
  const token = init.authToken === undefined ? getToken() : init.authToken
  let res: Response
  try {
    res = await fetchWithTimeout(`${base}${path}`, {
      method: init.method ?? (init.body === undefined ? 'GET' : 'POST'),
      headers: {
        ...(init.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    }, 20_000)
  } catch {
    throw new ApiError(0, t("Server bilan aloqa yo'q. Server manzili va tarmoqni tekshiring"))
  }
  if (!res.ok) {
    let msg = t('Xato ({n})', { n: res.status })
    try {
      const data = await res.json()
      if (typeof data.detail === 'string') msg = tServer(data.detail)
      else if (Array.isArray(data.detail)) msg = t("Ma'lumotlar noto'g'ri to'ldirilgan")
    } catch {
      /* keep default message */
    }
    throw new ApiError(res.status, msg)
  }
  return res.json() as Promise<T>
}
