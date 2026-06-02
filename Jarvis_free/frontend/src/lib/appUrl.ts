/** Базовый URL интерфейса (prod :8001 или Vite dev). */
export function appBaseUrl(): string {
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin
  }
  return 'http://127.0.0.1:8001'
}

export function appBaseUrlWithSlash(): string {
  return `${appBaseUrl()}/`
}
