import React from 'react'
import { buildReadinessReport, downloadReadinessJson, openPrintableReadinessReport } from '../lib/readinessReport'
import { PLATFORM } from '../lib/config'

export function ReadinessReportCard(props) {
  const report = buildReadinessReport(props)
  return (
    <div className="card readiness-tools no-print">
      <div className="readiness-tools-head">
        <div>
          <p className="label">Your progress</p>
          <h3 style={{ margin: '4px 0 6px' }}>Readiness report</h3>
          <p className="muted small" style={{ margin: 0, lineHeight: 1.55 }}>
            Export a tangible summary — completion, mock scores, weak chapters, and streak. Keep it for your own records or share with a preceptor.
          </p>
        </div>
        <p className="readiness-tools-pct">{report.readinessPercent}%</p>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
        <button type="button" className="btn" onClick={() => openPrintableReadinessReport(report)}>Print / save PDF summary</button>
        <button type="button" className="btn ghost" onClick={() => downloadReadinessJson(report)}>Download JSON</button>
      </div>
    </div>
  )
}

export function ReadinessCertificate({ readiness, doneCh, totalCh, accuracy, streak, examDate }) {
  if (readiness < 75) return null
  return (
    <div className="readiness-cert card">
      <div className="cert-inner">
        <p className="cert-eyebrow">Study milestone — not a board credential</p>
        <h2 className="cert-title">Exam readiness summary</h2>
        <p className="cert-name">{PLATFORM.name}</p>
        <p className="cert-pct">{readiness}%</p>
        <p className="cert-sub">Composite readiness (chapters · questions · flashcards)</p>
        <ul className="cert-stats">
          <li><strong>{doneCh}/{totalCh}</strong> chapters complete</li>
          <li><strong>{accuracy}%</strong> question accuracy</li>
          <li><strong>{streak}</strong> day streak</li>
          {examDate && (
            <li><strong>{new Date(examDate + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</strong> target exam</li>
          )}
        </ul>
        <p className="cert-foot small muted">Generated on this device · Built from official APEA 2026 course manuals for this cohort</p>
        <button type="button" className="btn ghost no-print cert-print" onClick={() => window.print()}>Print certificate card</button>
      </div>
    </div>
  )
}
