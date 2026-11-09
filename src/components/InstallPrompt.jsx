import { useEffect, useState } from 'react'

/**
 * Captures the browser's install prompt so a student can put the hub on their
 * home screen (and keep it working with no signal). Hidden once installed.
 */
export default function InstallPrompt() {
  const [event, setEvent] = useState(null)
  const [installed, setInstalled] = useState(
    () => typeof window !== 'undefined' && window.matchMedia?.('(display-mode: standalone)').matches,
  )
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem('apea-install-dismissed') === '1' } catch { return false }
  })

  useEffect(() => {
    const onPrompt = (e) => { e.preventDefault(); setEvent(e) }
    const onInstalled = () => { setInstalled(true); setEvent(null) }
    window.addEventListener('beforeinstallprompt', onPrompt)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  if (installed || dismissed || !event) return null

  async function install() {
    event.prompt()
    const { outcome } = await event.userChoice
    if (outcome === 'accepted') setInstalled(true)
    setEvent(null)
  }

  function dismiss() {
    try { localStorage.setItem('apea-install-dismissed', '1') } catch { /* ignore */ }
    setDismissed(true)
  }

  return (
    <div className="install-prompt no-print" role="region" aria-label="Install app">
      <div>
        <strong>Install on your phone</strong>
        <p className="small muted" style={{ margin: '2px 0 0' }}>
          Works offline once opened — study on breaks with no signal.
        </p>
      </div>
      <div className="install-actions">
        <button type="button" className="btn gold" onClick={install}>Install</button>
        <button type="button" className="btn ghost" onClick={dismiss}>Not now</button>
      </div>
    </div>
  )
}
