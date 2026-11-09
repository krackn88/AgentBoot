import React, { useEffect, useMemo, useState } from 'react'
import ManualContent from './ManualContent.jsx'
import { loadSearchIndex, searchDocs } from '../lib/search'
import { BookOpen, FileText, Search, ExternalLink, Download, ArrowLeft, AlertTriangle } from 'lucide-react'

const BASE = import.meta.env.BASE_URL
const PDF_BASE = '/apea/2026-fnp-manuals/'

function bytes(n) {
  if (!n) return '—'
  return n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`
}

export default function Manuals({ initialId }) {
  const [manifest, setManifest] = useState(null)
  const [module, setModule] = useState(null)
  const [text, setText] = useState('')
  const [tab, setTab] = useState('text')
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState([])
  const [chapterIndex, setChapterIndex] = useState(null)
  const [error, setError] = useState('')
  const [embedTried, setEmbedTried] = useState(false)

  useEffect(() => {
    fetch(`${BASE}data/content-index.json`).then(r => r.ok ? r.json() : null).then(setChapterIndex).catch(() => {})
  }, [])

  const moduleForChapterId = useMemo(() => {
    if (!manifest || !chapterIndex?.chapters) return {}
    const map = {}
    chapterIndex.chapters.forEach(ch => {
      const mid = String(ch.number + 1).padStart(2, '0')
      const m = manifest.modules.find(x => x.id === mid)
      if (m) map[ch.id] = m
    })
    return map
  }, [manifest, chapterIndex])

  useEffect(() => {
    let cancelled = false
    fetch(`${BASE}data/manuals.json`).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    }).then(data => {
      if (cancelled) return
      setManifest(data)
    }).catch(e => setError(`Could not load the manual catalog: ${e.message}`))
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!manifest) return
    if (!initialId) { setModule(null); setText(''); return }
    const found = manifest.modules.find(m => m.id === initialId)
    if (found && module?.id !== found.id) openModule(found, 'text', false)
  }, [manifest, initialId])

  async function openModule(m, mode = 'text', scroll = true) {
    setModule(m); setTab(mode); setError(''); setEmbedTried(false); setResults([])
    if (scroll) window.scrollTo(0, 0)
    if (typeof history !== 'undefined') history.replaceState(null, '', `#/manuals/${m.id}`)
    if (mode === 'text') {
      if (module?.id === m.id && text) return
      setText('')
      const filename = m.text_file.split('/').pop()
      try {
        const r = await fetch(`${BASE}data/manuals/${filename}`)
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        setText(await r.text())
      } catch (e) { setError(`Could not load ${m.title}: ${e.message}`) }
    }
  }

  function openPdf(url) {
    const w = window.open(url, '_blank', 'noopener,noreferrer')
    if (!w) window.location.href = url
  }

  function searchAll(e) {
    e?.preventDefault()
    const term = query.trim().toLowerCase()
    if (term.length < 3 || !manifest) return
    setSearching(true); setResults([]); setError('')
    loadSearchIndex()
      .then(docs => {
        const found = searchDocs(docs, term, 60)
          .filter(d => d.k === 'manual')
          .map(d => ({ module: moduleForChapterId[d.c] || manifest.modules.find(m => m.title === d.t), excerpt: `${d.s}: ${d.x}`.slice(0, 300), chapterId: d.c }))
          .filter(r => r.module)
        setResults(found)
        if (!found.length) setError('No matches in the manual text — try another term or browse manuals below.')
      })
      .catch(e => setError(`Search unavailable (${e.message}).`))
      .finally(() => setSearching(false))
  }

  const cleanText = useMemo(() => text.replace(/^---[\s\S]*?---\s*/, ''), [text])
  const totalChars = manifest ? manifest.modules.reduce((a, m) => a + m.text_chars, 0) : 0
  const totalPdf = manifest ? manifest.modules.reduce((a, m) => a + m.pdf_bytes, 0) : 0

  if (error && !manifest) return <div className="card"><h2>Manual Library</h2><p>{error}</p></div>

  if (module) {
    const pdf = `${PDF_BASE}${module.pdf_file}`
    const huge = module.pdf_bytes > 20 * 1024 * 1024
    return (
      <div className="manual-reader">
        <button className="btn ghost" onClick={() => { setModule(null); setText(''); setResults([]); history.replaceState(null, '', '#/manuals') }}>
          <ArrowLeft size={17} /> All manuals
        </button>
        <div className="manual-head">
          <div>
            <p className="label">Module {module.id} · Original APEA 2026 source</p>
            <h1>{module.title}</h1>
            <p className="muted">{module.text_chars.toLocaleString()} searchable characters · Original PDF {bytes(module.pdf_bytes)}</p>
          </div>
          <div className="manual-head-actions">
            <button type="button" className="btn" onClick={() => openPdf(pdf)}><ExternalLink size={17} /> Open original PDF</button>
            <a className="btn ghost" href={pdf} download={`${module.slug}.pdf`}><Download size={17} /> Download</a>
          </div>
        </div>
        <div className="segmented" role="tablist">
          <button type="button" role="tab" aria-selected={tab === 'text'} className={tab === 'text' ? 'active' : ''} onClick={() => { setTab('text'); if (!text) openModule(module, 'text', false) }}><FileText size={17} /> Full searchable text</button>
          <button type="button" role="tab" aria-selected={tab === 'pdf'} className={tab === 'pdf' ? 'active' : ''} onClick={() => setTab('pdf')}><BookOpen size={17} /> Original PDF</button>
        </div>
        {error && <div className="card warn"><AlertTriangle size={16} /> {error}</div>}
        {tab === 'text' ? (
          text ? <ManualContent text={cleanText} />
            : <div className="skeleton-card">Loading the complete manual…</div>
        ) : (
          <div className="pdf-panel">
            <div className="pdf-cta">
              <div>
                <h3 style={{ margin: 0 }}>Page-accurate original manual</h3>
                <p className="muted" style={{ margin: '6px 0 0' }}>
                  This is the real APEA course PDF ({bytes(module.pdf_bytes)}).
                  {huge ? ' Large manuals open most reliably in a new tab or download — in-browser embedding can choke on 50–170 MB files.' : ' Open it in a new tab for the cleanest reader, or try the in-page embed below.'}
                </p>
              </div>
              <div className="manual-head-actions">
                <button type="button" className="btn" onClick={() => openPdf(pdf)}><ExternalLink size={17} /> Open in new tab</button>
                <a className="btn ghost" href={pdf} download={`${module.slug}.pdf`}><Download size={17} /> Download PDF</a>
                {!embedTried && <button type="button" className="btn ghost" onClick={() => setEmbedTried(true)}>Try in-page embed</button>}
              </div>
            </div>
            {embedTried && (
              <div className="pdf-shell">
                <object data={pdf} type="application/pdf" aria-label={`${module.title} PDF`}>
                  <div className="pdf-fallback">
                    <p>Your browser blocked the in-page PDF viewer.</p>
                    <button type="button" className="btn" onClick={() => openPdf(pdf)}>Open {module.title} PDF</button>
                  </div>
                </object>
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div>
      <div className="manual-hero compact">
        <div>
          <p className="eyebrow">Complete source library</p>
          <h1>All 22 original APEA manuals</h1>
          <p>Full searchable text for every module, plus the original page-accurate PDFs — tables, diagrams, clinical pearls and practice content included.</p>
        </div>
        <div className="source-proof">
          <span><strong>22</strong> manuals</span>
          <span><strong>{(totalPdf / 1e9).toFixed(1)} GB</strong> PDFs</span>
          <span><strong>{Math.round(totalChars / 1000)}K</strong> characters</span>
        </div>
      </div>

      <form className="source-search" onSubmit={searchAll}>
        <Search size={20} />
        <input id="manual-search" name="manual-search" aria-label="Search all original manuals" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search 4,000+ indexed manual snippets: doses, criteria, diagnoses…" />
        <button className="btn" disabled={query.trim().length < 3 || searching}>{searching ? 'Searching…' : 'Search library'}</button>
      </form>

      {results.length > 0 && <section>
        <div className="section-title">
          <div><p className="eyebrow">Full-corpus search</p><h2>{results.length} results for “{query}”</h2></div>
          <button className="btn ghost" onClick={() => setResults([])}>Clear</button>
        </div>
        <div className="search-results">{results.map((r, i) => (
          <button key={`${r.module.id}-${r.at}-${i}`} className="search-result" onClick={() => openModule(r.module)}>
            <span className="module-badge">{r.module.id}</span>
            <span><strong>{r.module.title}</strong><small>{r.excerpt}</small></span>
            <ExternalLink size={16} />
          </button>
        ))}</div>
      </section>}

      <div className="section-title">
        <div><p className="eyebrow">2026 FNP video review course</p><h2>Original course manuals</h2></div>
      </div>
      <div className="manual-grid">
        {(manifest?.modules || []).map(m => (
          <article className="manual-card" key={m.id}>
            <div className="manual-number">{m.id}</div>
            <div>
              <h3>{m.title}</h3>
              <p>{(m.text_chars / 1000).toFixed(0)}K characters · {bytes(m.pdf_bytes)} PDF</p>
            </div>
            <div className="manual-actions">
              <button type="button" onClick={() => openModule(m, 'text')}><FileText size={16} /> Read full text</button>
              <button type="button" onClick={() => openPdf(`${PDF_BASE}${m.pdf_file}`)}><BookOpen size={16} /> Open PDF</button>
            </div>
          </article>
        ))}
      </div>
      {!manifest && <div className="skeleton-card">Loading the complete manual catalog…</div>}
    </div>
  )
}
