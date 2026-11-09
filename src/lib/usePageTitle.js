import { useEffect } from 'react'
import { PLATFORM } from './config'

const BASE = PLATFORM.short

export function usePageTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} · ${BASE}` : `${BASE} — APEA 2026`
    return () => { document.title = `${BASE} — APEA 2026 Study Platform` }
  }, [title])
}
