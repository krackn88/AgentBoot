import React, { useMemo, useState } from 'react'
import { Blocks } from './Reader.jsx'
import { PageHeader } from './AppShell.jsx'
import { Search, Printer, Zap } from 'lucide-react'

/**
 * High-yield review page.
 *
 * The previous version rendered one Overview table, a labs table, and a static
 * dozen pearls — while claiming to show "the highest-signal lines pulled from all
 * 22 course manuals." It now surfaces the full must-know rule table, every
 * lab value, and every pearl by chapter, with a filter over the whole set.
 */
export default function HighYield({ guide, pearls = [], onGo }) {
  const [query, setQuery] = useState('')

  const ruleTables = useMemo(
    () => (guide.quickRef?.sections || []).flatMap(s => s.blocks.filter(b => b.type === 'table').map(b => ({ section: s.title, ...b }))),
    [guide],
  )

  const labsSections = useMemo(
    () => (guide.chapters[0]?.sections || []).filter(s => /labs/i.test(s.title)),
    [guide],
  )

  const pearlsByChapter = useMemo(() => {
    const map = new Map()
    pearls.forEach(p => {
      const key = p.tag || p.chapterId || 'General'
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(p)
    })
    return [...map.entries()].sort((a, b) => b[1].length - a[1].length)
  }, [pearls])

  const q = query.trim().toLowerCase()
  const match = text => !q || String(text).toLowerCase().includes(q)

  const filteredRules = ruleTables
    .map(t => ({ ...t, rows: t.rows.filter(r => match(r.join(' '))) }))
    .filter(t => t.rows.length)

  const filteredPearls = pearlsByChapter
    .map(([chapter, list]) => [chapter, list.filter(p => match(p.front))])
    .filter(([, list]) => list.length)

  const totalShown = filteredRules.reduce((a, t) => a + t.rows.length, 0) + filteredPearls.reduce((a, [, l]) => a + l.length, 0)

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <PageHeader
        eyebrow="High yield"
        title="Quick reference + clinical pearls"
        subtitle="The must-know numbers and rules from the study guide, labs worth memorising, and every clinical pearl extracted from the course manuals. Filter the whole set below."
        actions={(
          <button type="button" className="btn ghost no-print" onClick={() => window.print()}>
            <Printer size={16} /> Print
          </button>
        )}
      />

      <div className="hy-search no-print">
        <Search size={18} aria-hidden />
        <input
          type="search"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Filter — amoxicillin, eGFR, preeclampsia, vaccines…"
          aria-label="Filter high-yield content"
        />
        {query && <span className="small muted">{totalShown} matches</span>}
      </div>

      {filteredRules.length > 0 && (
        <section className="hy-section">
          <h2 className="hy-h2"><Zap size={18} /> Must-know numbers and rules</h2>
          {filteredRules.map((t, i) => (
            <div key={i} className="card" style={{ marginBottom: 14, padding: 0 }}>
              <div className="tablewrap">
                <table className="hy-table">
                  <thead><tr>{t.headers.map((h, j) => <th key={j}>{h}</th>)}</tr></thead>
                  <tbody>
                    {t.rows.map((r, j) => (
                      <tr key={j}>{r.map((c, k) => <td key={k}>{k === 0 ? <strong>{c}</strong> : c}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </section>
      )}

      {labsSections.length > 0 && (
        <section className="hy-section">
          <h2 className="hy-h2">Labs to commit to memory</h2>
          {labsSections.map(s => (
            <div key={s.id} className="card" style={{ marginBottom: 14 }}>
              <Blocks blocks={s.blocks} />
            </div>
          ))}
        </section>
      )}

      {filteredPearls.length > 0 && (
        <section className="hy-section">
          <h2 className="hy-h2">Clinical pearls by chapter</h2>
          <p className="small muted" style={{ marginTop: -4, marginBottom: 12 }}>
            {pearls.length} pearls extracted from the course manuals. Drill them as spaced-repetition cards in Flashcards.
          </p>
          {filteredPearls.map(([chapter, list]) => (
            <div key={chapter} className="card hy-pearl-group">
              <p className="label">{chapter} · {list.length}</p>
              <ol className="hy-pearls">
                {list.map(p => <li key={p.id}>{p.front}</li>)}
              </ol>
            </div>
          ))}
        </section>
      )}

      {q && !totalShown && (
        <div className="card">Nothing in the high-yield set matches “{query}”. Try the full search on the dashboard — it covers every manual line.</div>
      )}

      <div className="card hy-footer no-print">
        <strong>Want these as recall cards?</strong>
        <p className="muted small" style={{ margin: '4px 0 12px' }}>
          The pearl deck and the high-yield table deck both run on spaced repetition, so cards return right before you would forget them.
        </p>
        <button type="button" className="btn" onClick={() => onGo('flashcards')}>Open flashcards →</button>
      </div>
    </div>
  )
}
