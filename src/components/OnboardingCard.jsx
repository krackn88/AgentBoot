import React, { useState } from 'react'
import { X } from 'lucide-react'

const KEY = 'apea-onboarding-dismissed'

export default function OnboardingCard({ onGo }) {
  const [open, setOpen] = useState(() => !localStorage.getItem(KEY))
  if (!open) return null

  function dismiss() {
    localStorage.setItem(KEY, '1')
    setOpen(false)
  }

  const steps = [
    { n: 1, title: 'Read & mark complete', body: 'Work through guide chapters (manual depth + pearls in each). Hit complete when done.', action: () => onGo('library'), label: 'Open study guide' },
    { n: 2, title: 'Practice immediately', body: 'Do chapter questions and workbook drills — missed items feed your personal flashcard deck.', action: () => onGo('quiz'), label: 'Question bank' },
    { n: 3, title: 'Mock weekly, track readiness', body: 'Run timed mocks, follow the 12-week path, and export your readiness report before exam day.', action: () => onGo('tests'), label: 'Mock exams' },
  ]

  return (
    <div className="card onboarding-card no-print" role="region" aria-label="Getting started">
      <button type="button" className="onboarding-close" onClick={dismiss} aria-label="Dismiss"><X size={18} /></button>
      <p className="label">New here?</p>
      <h3 style={{ margin: '4px 0 10px' }}>How to use this platform in 3 steps</h3>
      <p className="muted small" style={{ margin: '0 0 14px', lineHeight: 1.55 }}>Built from official APEA 2026 course manuals hosted for this cohort — structured so you study, test, and see gaps instead of hunting PDFs.</p>
      <ol className="onboarding-steps">
        {steps.map(s => (
          <li key={s.n}>
            <span className="onboarding-num">{s.n}</span>
            <div>
              <strong>{s.title}</strong>
              <p className="small muted" style={{ margin: '4px 0 8px', lineHeight: 1.5 }}>{s.body}</p>
              <button type="button" className="btn ghost" style={{ padding: '6px 12px', fontSize: 13 }} onClick={s.action}>{s.label} →</button>
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
