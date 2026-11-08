import React, { useEffect, useRef, useState } from 'react'
import { pdfUrlForChapter } from '../lib/pdfs'

export function Blocks({ blocks }) {
  return blocks.map((b, i) => {
    if (b.type === 'p') return <p key={i}>{b.text}</p>
    if (b.type === 'list') return <ul key={i}>{b.items.map((it, j) => <li key={j}>{it}</li>)}</ul>
    if (b.type === 'table') return (
      <div className="tablewrap" key={i}><table><thead><tr>{b.headers.map((h, j) => <th key={j}>{h}</th>)}</tr></thead>
      <tbody>{b.rows.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{c}</td>)}</tr>)}</tbody></table></div>)
    return null
  })
}

export default function Reader({ chapter, store, update, onBack, onQuiz, onNext, onOpenManual }) {
  const done = !!store.completed[chapter.id]
  const ref = useRef(null)
  const [progress, setProgress] = useState(0)
  useEffect(() => { window.scrollTo(0, 0) }, [chapter.id])
  useEffect(() => {
    function onScroll() { const h = document.documentElement; const max = h.scrollHeight - h.clientHeight; setProgress(max > 0 ? Math.min(100, Math.round(h.scrollTop / max * 100)) : 0) }
    window.addEventListener('scroll', onScroll, { passive: true }); onScroll(); return () => window.removeEventListener('scroll', onScroll)
  }, [chapter.id])
  const toggleDone = () => update(s => ({
    ...s, lastChapter: chapter.id,
    completed: { ...s.completed, [chapter.id]: !done },
    studyDates: [...new Set([...s.studyDates, new Date().toISOString().slice(0, 10)])],
  }))
  const bookmarked = store.bookmarks.includes(chapter.id)
  return (
    <div className="reader" ref={ref} style={{ fontSize: store.fontSize }}>
      <div style={{ position: 'sticky', top: 0, zIndex: 5, background: 'var(--bg)', padding: '8px 0' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><button className="btn ghost" onClick={onBack}>← All chapters</button>
        <button className="btn ghost" onClick={() => window.print()}>Print / save PDF</button><span className="small muted">{progress}% read</span></div>
        <div className="bar" style={{ marginTop: 8 }}><i style={{ width: progress + '%' }} /></div>
      </div>
      <p className="label" style={{ marginTop: 20 }}>Chapter {chapter.number} · ~{Math.max(1, Math.round(chapter.wordCount / 200))} min read · {chapter.questions.length} practice questions</p>
      <h1 style={{ fontSize: 34, margin: '6px 0' }}>{chapter.shortTitle}</h1>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '14px 0 6px' }}>
        <button className="btn" onClick={toggleDone}>{done ? '✓ Completed — tap to undo' : 'Mark chapter complete'}</button>
        <button className="btn ghost" onClick={() => update(s => ({ ...s, bookmarks: bookmarked ? s.bookmarks.filter(b => b !== chapter.id) : [...s.bookmarks, chapter.id] }))}>{bookmarked ? '★ Bookmarked' : '☆ Bookmark'}</button>
        {chapter.questions.length > 0 && <button className="btn gold" onClick={() => onQuiz(chapter.id)}>Practice this chapter →</button>}
        {onOpenManual && <button className="btn ghost" onClick={onOpenManual}>Open full original manual</button>}
        <a className="btn ghost" href={pdfUrlForChapter(chapter)} target="_blank" rel="noreferrer">Open chapter PDF</a>
        <select style={{ width: 'auto' }} value={store.fontSize} onChange={e => update({ fontSize: Number(e.target.value) })} aria-label="Text size">
          <option value={15}>Text S</option><option value={17}>Text M</option><option value={19}>Text L</option>
        </select>
      </div>
      <div className="card" style={{ margin: '14px 0' }}><strong>In this chapter</strong>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {chapter.sections.map(s => <a key={s.id} className="pill" href={`#${s.id}`} onClick={e => { e.preventDefault(); document.getElementById(s.id)?.scrollIntoView({ behavior: 'smooth' }) }}>{s.title}</a>)}
        </div></div>
      {chapter.sections.map(sec => (
        <section key={sec.id} id={sec.id}><h3>{sec.title}</h3><Blocks blocks={sec.blocks} /></section>
      ))}
      <div style={{ display: 'flex', gap: 8, marginTop: 36, flexWrap: 'wrap' }}>
        <button className="btn" onClick={toggleDone}>{done ? '✓ Completed' : 'Mark complete & continue'}</button>
        {onNext && <button className="btn ghost" onClick={onNext}>Next chapter →</button>}
      </div>
    </div>
  )
}
