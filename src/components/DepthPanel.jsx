import React, { useState } from 'react'

/**
 * The manual's reference material, cleaned up.
 *
 * The PDF extracts are mostly slide fragments; only a small share is trustworthy
 * prose. Rather than pad the tab with broken sentences, this shows the three
 * things that survived extraction cleanly — real tables rebuilt from the page's
 * column geometry, complete clinical statements, and the raw source on demand
 * under a clearly-labelled disclosure.
 */
export default function DepthPanel({ module, chapter, err }) {
  const [showRaw, setShowRaw] = useState(false)
  const ref = module?.reference
  const tables = ref?.tables ?? []
  const statements = ref?.statements ?? []
  const fragments = ref?.fragments ?? []
  const pearls = module?.pearls ?? []

  const empty = !err && module && !tables.length && !statements.length && !fragments.length

  return (
    <div className="depth-panel">
      <div className="depth-intro">
        <p className="muted" style={{ margin: 0, lineHeight: 1.6 }}>
          Rebuilt from the original APEA course manual for{' '}
          <strong>{module?.manualTitle || chapter.shortTitle}</strong>. Tables are reconstructed from the
          slide layout — verify anything high-stakes against the PDF.
        </p>
        <div className="depth-counts">
          <span className="pill">{tables.length} tables</span>
          <span className="pill">{statements.length} statements</span>
          <span className="pill">{pearls.length} pearls</span>
        </div>
      </div>

      {err && <div className="card warn">{err}</div>}
      {!module && !err && <div className="skeleton-card">Loading manual reference…</div>}
      {empty && <div className="card">No reference material could be recovered for this chapter. Use the PDF.</div>}

      {tables.length > 0 && (
        <section className="depth-block">
          <h2 className="depth-h2">Reference tables</h2>
          <p className="small muted depth-note">
            Sliced back into their original columns. Empty cells mean the source slide left them blank.
          </p>
          {tables.map((t, i) => (
            <figure key={i} className="depth-table card">
              <figcaption>
                <span className="label">{t.section || 'Manual table'}</span>
                <strong>{t.title || t.headers.join(' · ')}</strong>
              </figcaption>
              <div className="tablewrap">
                <table>
                  <thead>
                    <tr>{t.headers.map((h, j) => <th key={j}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {t.rows.map((r, j) => (
                      <tr key={j}>{r.map((c, k) => <td key={k}>{c}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </figure>
          ))}
        </section>
      )}

      {statements.length > 0 && (
        <section className="depth-block">
          <h2 className="depth-h2">Complete teaching points</h2>
          <p className="small muted depth-note">
            Sentences that survived extraction intact — tips, criteria, dosing, and referral triggers.
          </p>
          <ul className="depth-statements card">
            {statements.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </section>
      )}

      {fragments.length > 0 && (
        <section className="depth-block">
          <h2 className="depth-h2">Raw slide lines</h2>
          <p className="small muted depth-note">
            {fragments.length} extracted lines from the source slides. Kept for search and cross-checking —
            they are fragments of slide text, not edited prose.
          </p>
          <button type="button" className="btn ghost" onClick={() => setShowRaw(v => !v)}>
            {showRaw ? 'Hide raw lines' : `Show ${fragments.length} raw lines`}
          </button>
          {showRaw && (
            <div className="depth-raw">
              <ol>{fragments.map((f, i) => <li key={i}>{f}</li>)}</ol>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
