import React, { useEffect, useMemo, useState } from 'react'
import { Search as SearchIcon, X, Loader2 } from 'lucide-react'
import { loadSearchIndex, searchDocs, highlight } from '../lib/search'

const KINDS = [
  { id: 'all', label: 'Everything' },
  { id: 'manual', label: 'Manuals' },
  { id: 'guide', label: 'Study guide' },
  { id: 'pearl', label: 'Pearls' },
  { id: 'question', label: 'Questions' },
  { id: 'rationale', label: 'Rationales' },
]

function Highlighted({ text, query }) {
  return highlight(text, query).map((part, i) =>
    part.hit ? <mark key={i}>{part.text}</mark> : <React.Fragment key={i}>{part.text}</React.Fragment>,
  )
}

/**
 * Full-content search. Loads the 13k-document index on first focus (not on page
 * load), so it stays instant to open and covers every manual line, not a sample.
 */
export default function SearchPanel({ onOpenChapter, onOpenManual, autoFocus = false }) {
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState('all')
  const [docs, setDocs] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [partial, setPartial] = useState(true)

  useEffect(() => {
    if (docs || loading) return
    setLoading(true)
    loadSearchIndex((fresh, status) => {
      setDocs([...fresh])
      setPartial(!status.complete)
    })
      .catch(e => setError(`Search index unavailable (${e.message}).`))
      .finally(() => setLoading(false))
  }, [docs, loading])

  const results = useMemo(() => {
    if (!docs || query.trim().length < 2) return []
    const all = searchDocs(docs, query, kind === 'all' ? 60 : 200)
    const filtered = kind === 'all' ? all : all.filter(d => d.k === kind)
    return filtered.slice(0, 60)
  }, [docs, query, kind])

  const counts = useMemo(() => {
    if (!docs || query.trim().length < 2) return {}
    const all = searchDocs(docs, query, 400)
    return all.reduce((acc, d) => ({ ...acc, [d.k]: (acc[d.k] || 0) + 1 }), {})
  }, [docs, query])

  const grouped = useMemo(() => {
    const map = new Map()
    results.forEach(d => {
      const key = d.c
      if (!map.has(key)) map.set(key, { title: d.t, items: [] })
      map.get(key).items.push(d)
    })
    return [...map.values()]
  }, [results])

  return (
    <div className="search-panel">
      <div className="search-field">
        <SearchIcon size={19} aria-hidden />
        <input
          type="search"
          value={query}
          autoFocus={autoFocus}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search every manual, chapter, pearl, and rationale — torsades, CURB-65, A1c…"
          aria-label="Search all content"
        />
        {loading && <Loader2 size={17} className="spin" aria-label="Loading index" />}
        {query && <button type="button" className="search-clear" onClick={() => setQuery('')} aria-label="Clear"><X size={16} /></button>}
      </div>

      {error && <p className="small" style={{ color: 'var(--red)' }}>{error}</p>}

      {query.trim().length >= 2 && (
        <div className="search-filters">
          {KINDS.map(k => {
            const n = k.id === 'all' ? results.length : counts[k.id] || 0
            return (
              <button
                key={k.id}
                type="button"
                className={`search-chip ${kind === k.id ? 'active' : ''}`}
                onClick={() => setKind(k.id)}
                disabled={k.id !== 'all' && !n}
              >
                {k.label}{n ? ` ${n}` : ''}
              </button>
            )
          })}
        </div>
      )}

      {query.trim().length >= 2 && (
        <p className="small muted search-summary">
          {results.length
            ? `${results.length}${results.length === 60 ? '+' : ''} results across ${grouped.length} chapter${grouped.length === 1 ? '' : 's'}`
            : partial
              ? 'Searching…'
              : 'No matches. Try a drug class, lab value, or condition.'}
          {partial && results.length > 0 && <span className="search-streaming"> · still loading manual text…</span>}
        </p>
      )}

      {grouped.map(g => (
        <section key={g.title} className="search-group">
          <h3 className="search-group-title">{g.title}</h3>
          {g.items.map(d => (
            <button
              key={d.i}
              type="button"
              className="search-item"
              onClick={() => (d.k === 'manual' ? onOpenManual?.(d.c) : onOpenChapter?.(d.c))}
            >
              <span className={`search-kind kind-${d.k}`}>{d.k}</span>
              <span className="search-item-body">
                {d.s && <span className="search-item-section">{d.s}</span>}
                <span className="search-item-text"><Highlighted text={d.x} query={query} /></span>
              </span>
            </button>
          ))}
        </section>
      ))}
    </div>
  )
}
