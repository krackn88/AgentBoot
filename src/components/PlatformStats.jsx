import React from 'react'

/** At-a-glance content depth — shown on Dashboard and About. */
export default function PlatformStats({ guide, contentMeta, manualBank, questionTotal }) {
  const guideQ = guide?.meta?.questions ?? 0
  const manualGraded = manualBank?.meta?.graded ?? 0
  const manualTotal = manualBank?.meta?.total ?? 0
  const pearls = contentMeta?.pearls_total ?? 0
  const depthWords = contentMeta?.chapters?.reduce((a, c) => a + (c.words || 0), 0) ?? 0
  const manualPct = manualTotal ? Math.round((manualGraded / manualTotal) * 100) : 0

  const items = [
    { label: 'Graded questions', value: (questionTotal || guideQ + manualGraded).toLocaleString(), sub: `${guideQ} guide · ${manualGraded} manual slides` },
    { label: 'Clinical pearls', value: pearls.toLocaleString(), sub: 'Flashcards + chapter tabs' },
    { label: 'Manual depth', value: depthWords ? `${Math.round(depthWords / 1000)}K` : '—', sub: 'Words extracted from course manuals' },
    { label: 'Slide bank keyed', value: manualTotal ? `${manualPct}%` : '—', sub: manualTotal ? `${manualGraded} of ${manualTotal} slide MCQs` : 'Syncing…' },
  ]

  return (
    <div className="platform-stats no-print" role="region" aria-label="Platform content">
      {items.map(it => (
        <div key={it.label} className="platform-stat">
          <p className="label">{it.label}</p>
          <p className="platform-stat-val">{it.value}</p>
          <p className="small muted" style={{ margin: '4px 0 0', lineHeight: 1.4 }}>{it.sub}</p>
        </div>
      ))}
    </div>
  )
}
