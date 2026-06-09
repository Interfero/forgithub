import { useEffect } from 'react'

/** Частый опрос статуса, пока идёт загрузка. */
export function useDownloadPoll(
  active: boolean,
  onPoll: () => void | Promise<void>,
  intervalMs = 1000,
) {
  useEffect(() => {
    if (!active) return
    void onPoll()
    const id = window.setInterval(() => void onPoll(), intervalMs)
    return () => window.clearInterval(id)
  }, [active, onPoll, intervalMs])
}
