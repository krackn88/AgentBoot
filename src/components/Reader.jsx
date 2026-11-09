import React, { useEffect, useRef, useState } from 'react'
import { pdfUrlForChapter } from '../lib/pdfs'
import { loadChapterModule } from '../lib/platform'
import ChapterPrintPacket from './ChapterPrintPacket.jsx'
import DepthPanel from './DepthPanel.jsx'

export function Blocks({ blocks }) {
  return blocks.map((b, i) => {
    if (b.type === 'manual-note') return (
      <aside className="manual-note" key={i}>
        <p className="label">From the course manual{b.source ? ` · ${b.source}` : ''}</p>
        <p>{b.text}</p>
      </aside>
    )
    if (b.type === 'p') return <p key={i}>{b.text}</p>
    if (b.type === 'list' || b.type === 'manual-list') return (
      <ul key={i} className={b.type === 'manual-list' ? 'manual-list' : undefined}>{b.items.map((it, j) => <li key={j}>{it}</li>)}</ul>
    )
    if (b.type === 'table') return (
      <div className="tablewrap" key={i}><table><thead><tr>{b.headers.map((h, j) => <th key={j}>{h}</th>)}</tr></thead>
      <tbody>{b.rows.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{c}</td>)}</tr>)}</tbody></table></div>)
    return null
  })
}

export default function Reader({ chapter, store, update, onBack, onQuiz, onNext, onOpenManual, pearlCards = [] }) {
  const done = !!store.completed[chapter.id]
  const ref = useRef(null)
  const [progress, setProgress] = useState(0)
  const [tab, setTab] = useState('guide')
  const [module, setModule] = useState(null)
  const [modErr, setModErr] = useState('')
  const [printingPacket, setPrintingPacket] = useState(false)
  const chapterPearls = pearlCards.filter(p => p.chapterId === chapter.id)

  useEffect(() => { window.scrollTo(0, 0); setTab('guide') }, [chapter.id])
  useEffect(() => {
    let cancel = false
    setModule(null); setModErr('')
    loadChapterModule(chapter.id)
      .then(d => { if (!cancel) setModule(d) })
      .catch(e => { if (!cancel) setModErr(`Expanded manual notes unavailable (${e.message}).`) })
    return () => { cancel = true }
  }, [chapter.id])

  useEffect(() => {
    function onScroll() { const h = document.documentElement; const max = h.scrollHeight - h.clientHeight; setProgress(max > 0 ? Math.min(100, Math.round(h.scrollTop / max * 100)) : 0) }
    window.addEventListener('scroll', onScroll, { passive: true }); onScroll(); return () => window.removeEventListener('scroll', onScroll)
  }, [chapter.id, tab])

  const toggleDone = () => update(s => ({
    ...s, lastChapter: chapter.id,
    completed: { ...s.completed, [chapter.id]: !done },
    studyDates: [...new Set([...s.studyDates, new Date().toISOString().slice(0, 10)])],
  }))
  const bookmarked = store.bookmarks.includes(chapter.id)

  return (
    <div className={`reader ${printingPacket ? 'is-print-packet' : ''}`} ref={ref} style={{ fontSize: store.fontSize }}>
      <div className="reader-sticky no-print">
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button type="button" className="btn ghost" onClick={onBack}>← All chapters</button>
          <button type="button" className="btn ghost" onClick={() => { setPrintingPacket(true); setTimeout(() => { window.print(); setPrintingPacket(false) }, 120) }}>Print study packet</button>
          <span className="small muted">{progress}% read</span>
        </div>
        <div className="bar" style={{ marginTop: 8 }}><i style={{ width: progress + '%' }} /></div>
      </div>

      <p className="label" style={{ marginTop: 16 }}>Chapter {chapter.number} · {chapter.questions.length} practice questions
        {module?.meta && <> · <strong>{module.meta.table_count ?? 0}</strong> manual tables · <strong>{module.meta.pearl_count}</strong> pearls</>}</p>
      <h1 className="reader-title">{chapter.shortTitle}</h1>

      <div className="reader-actions no-print">
        <button type="button" className="btn" onClick={toggleDone}>{done ? '✓ Completed' : 'Mark complete'}</button>
        <button type="button" className="btn ghost" onClick={() => update(s => ({ ...s, bookmarks: bookmarked ? s.bookmarks.filter(b => b !== chapter.id) : [...s.bookmarks, chapter.id] }))}>{bookmarked ? '★ Saved' : '☆ Bookmark'}</button>
        {chapter.questions.length > 0 && <button type="button" className="btn" onClick={() => onQuiz(chapter.id)}>Chapter quiz</button>}
        {onOpenManual && <button type="button" className="btn ghost" onClick={onOpenManual}>Original manual</button>}
        <a className="btn ghost" href={pdfUrlForChapter(chapter)} target="_blank" rel="noreferrer">PDF</a>
        <select style={{ width: 'auto' }} value={store.fontSize} onChange={e => update({ fontSize: Number(e.target.value) })} aria-label="Text size">
          <option value={15}>S</option><option value={17}>M</option><option value={19}>L</option>
        </select>
      </div>

      <div className="segmented reader-tabs no-print" role="tablist">
        <button type="button" role="tab" className={tab === 'guide' ? 'active' : ''} onClick={() => setTab('guide')}>Study guide</button>
        <button type="button" role="tab" className={tab === 'depth' ? 'active' : ''} onClick={() => setTab('depth')}>Course manual depth</button>
        <button type="button" role="tab" className={tab === 'pearls' ? 'active' : ''} onClick={() => setTab('pearls')}>Clinical pearls ({chapterPearls.length})</button>
      </div>

      {tab === 'guide' && (
        <>
          <div className="card reader-toc"><strong>In this chapter</strong>
            <div className="toc-pills">{chapter.sections.map(s => (
              <a key={s.id} className="pill" href={`#${s.id}`} onClick={e => { e.preventDefault(); document.getElementById(s.id)?.scrollIntoView({ behavior: 'smooth' }) }}>{s.title}</a>
            ))}</div></div>
          {chapter.sections.map(sec => (
            <section key={sec.id} id={sec.id} className="reader-section"><h3>{sec.title}</h3><Blocks blocks={sec.blocks} /></section>
          ))}
        </>
      )}

      {tab === 'depth' && <DepthPanel module={module} chapter={chapter} err={modErr} />}

      {tab === 'pearls' && (
        <div className="pearls-panel">
          <p className="muted">
            Reviewed pearls for this chapter — whole statements with a number, threshold or first-line rule.
            Every card is also drilled in the spaced-repetition deck.
          </p>
          {chapterPearls.length === 0 && (
            <div className="card" style={{ marginTop: 12 }}>
              No reviewed pearls for this chapter yet. The reference tables in <strong>Course manual depth</strong> carry
              its highest-yield numbers, and the original PDF is one tap away.
            </div>
          )}
          <div className="pearl-grid">{chapterPearls.map((p, i) => (
            <div key={p.id || i} className="pearl-card"><span className="pearl-num">{i + 1}</span><p>{p.front || p}</p></div>
          ))}</div>
        </div>
      )}

      <div className="reader-foot no-print">
        <button type="button" className="btn" onClick={toggleDone}>{done ? '✓ Completed' : 'Mark complete & continue'}</button>
        {onNext && <button type="button" className="btn ghost" onClick={onNext}>Next chapter →</button>}
      </div>
      {(printingPacket || module) && (
        <div className="print-packet-root" aria-hidden={!printingPacket}>
          <ChapterPrintPacket chapter={chapter} module={module} pearls={chapterPearls} />
        </div>
      )}
    </div>
  )
}
