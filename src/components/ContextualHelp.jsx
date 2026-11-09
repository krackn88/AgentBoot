import React, { useId, useState } from 'react'
import { CircleHelp } from 'lucide-react'

const COPY = {
  dashboard: {
    title: 'Dashboard in 30 seconds',
    bullets: [
      'Readiness % blends chapters, questions, and flashcards — not just pages read.',
      'Start with “Continue studying,” then hit practice questions in the same chapter.',
      'Export your readiness report before exam day (print/PDF button on this page).',
    ],
  },
  tests: {
    title: 'Mock exams',
    bullets: [
      'Run one full-length mock per week at board pace (timer enforced).',
      '75%+ on recent mocks is the same target as the Answer Key suggests for passing.',
      'Review rationales after every run — missed items also land in your flashcard deck.',
    ],
  },
  reader: {
    title: 'Chapter reader',
    bullets: [
      'Use Guide for the condensed path; Course depth & pearls tabs add manual detail.',
      'Mark complete when you finish — it updates your readiness score.',
      'Practice questions link to the same chapter in the question bank.',
    ],
  },
}

export default function ContextualHelp({ view }) {
  const copy = COPY[view]
  const [open, setOpen] = useState(false)
  const panelId = useId()
  if (!copy) return null

  return (
    <div className="contextual-help no-print">
      <button
        type="button"
        className="help-trigger"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(o => !o)}
        title="Help"
      >
        <CircleHelp size={18} aria-hidden />
        <span>Help</span>
      </button>
      {open && (
        <div id={panelId} className="help-panel" role="region" aria-label={copy.title}>
          <p className="label" style={{ margin: 0 }}>{copy.title}</p>
          <ul>{copy.bullets.map(b => <li key={b}>{b}</li>)}</ul>
          <button type="button" className="btn ghost help-close" onClick={() => setOpen(false)}>Got it</button>
        </div>
      )}
    </div>
  )
}
