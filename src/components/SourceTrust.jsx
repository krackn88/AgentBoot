import React from 'react'
import { FileCheck, Database, Shield } from 'lucide-react'

/** Skeptic-friendly: what this is, where content came from, and what we do not do. */
export default function SourceTrust({ guide, manualBank, totalQ, guideQ, manualQ }) {
  const manualTotal = manualBank?.meta?.total ?? 0
  const manualGraded = manualBank?.meta?.graded ?? 0
  const manualKeyed = manualTotal > 0 && manualGraded === manualTotal

  return (
    <section className="card source-trust no-print" aria-label="Content sources">
      <div className="source-trust-head">
        <p className="label" style={{ margin: 0 }}>What this is</p>
        <h2 className="source-trust-title">Official APEA 2026 cohort materials — organized, not rewritten</h2>
      </div>
      <div className="source-trust-grid">
        <div className="source-trust-item">
          <FileCheck size={20} strokeWidth={2} aria-hidden />
          <div>
            <strong>Same manuals &amp; answer key</strong>
            <p className="small muted" style={{ margin: '4px 0 0', lineHeight: 1.5 }}>
              Study guide chapters, 22 full course manuals, and PDF links from this server. Text is extracted for search and study modes; original PDFs are one tap away on every chapter.
            </p>
          </div>
        </div>
        <div className="source-trust-item">
          <Database size={20} strokeWidth={2} aria-hidden />
          <div>
            <strong>{totalQ.toLocaleString()} graded MCQs</strong>
            <p className="small muted" style={{ margin: '4px 0 0', lineHeight: 1.5 }}>
              {guideQ} from the study guide Answer Key · {manualQ} from course-manual slides
              {manualKeyed ? ' — all slide items keyed for auto-grade' : manualTotal ? ` · ${manualGraded}/${manualTotal} slide MCQs keyed` : ''}.
              Practice mode shows rationales after each item.
            </p>
          </div>
        </div>
        <div className="source-trust-item">
          <Shield size={20} strokeWidth={2} aria-hidden />
          <div>
            <strong>No login · no paywall during beta</strong>
            <p className="small muted" style={{ margin: '4px 0 0', lineHeight: 1.5 }}>
              Progress lives in your browser only. Readiness % is a study tracker, not a board score. Mocks use the same keyed items — 75% is the passing target APEA cites in the Answer Key context.
            </p>
          </div>
        </div>
      </div>
      {guide?.meta?.source && (
        <p className="small muted source-trust-foot" style={{ margin: '14px 0 0', lineHeight: 1.5 }}>
          Guide source: {guide.meta.source}
          {guide.meta.title ? ` · ${guide.meta.title}` : ''}
        </p>
      )}
    </section>
  )
}
