import React, { useMemo, useState } from 'react'
import { ArrowLeft, Printer, PencilLine, Grid3x3, Stethoscope, NotebookPen, Eye, Check, X } from 'lucide-react'
import { bumpDaily, shuffle } from '../lib/store'

// Each table row becomes one recall prompt: show the row label + column header, hide the cell.
function tableDrills(chapter) {
  const out = []
  chapter.sections.forEach(s => s.blocks.forEach((b, bi) => {
    if (b.type !== 'table' || b.headers.length < 2) return
    b.rows.forEach((r, ri) => {
      if (!r[0]) return
      for (let ci = 1; ci < r.length; ci++) {
        const cell = (r[ci] || '').trim()
        if (!cell || cell === '—' || cell === '-' || cell.length > 260) continue
        out.push({ id: `${s.id}-t${bi}-r${ri}-c${ci}`, section: s.title, row: r[0], column: b.headers[ci] || `Column ${ci + 1}`, answer: cell, table: b })
      }
    })
  }))
  return out
}

function caseStudies(chapter) {
  return chapter.questions.filter(q => (q.correctIndex == null || q.options.length < 2) && q.explanation)
}

function chapterTables(chapter) {
  const out = []
  chapter.sections.forEach(s => s.blocks.forEach(b => { if (b.type === 'table') out.push({ section: s.title, ...b }) }))
  return out
}

/**
 * Recall drills built from the PDF bullet lists.
 *
 * The slides carry ~790 intact lists (lesion definitions, criteria, red flags,
 * dosing, differentials) that never reached a study surface before. Each becomes
 * one prompt-and-reveal drill so a student reproduces the list from memory.
 */
function listDrills(chapter, pdfLists = []) {
  return pdfLists
    .filter(l => l.chapterId === chapter.id)
    .map(l => ({
      id: l.id,
      section: l.section || chapter.shortTitle,
      row: l.prompt,
      column: `Recall all ${l.items.length} items`,
      answer: l.items.map((it, i) => `${i + 1}. ${it}`).join('\n'),
      kind: 'list',
      items: l.items,
      page: l.page,
    }))
}

export function workbookStats(guide, store) {
  const wb = store.workbook || {}
  let total = 0, done = 0
  guide.chapters.forEach(c => { const n = tableDrills(c).length; total += n; done += Math.min(n, Object.keys(wb[c.id]?.drills || {}).length) })
  return { total, done }
}

function pearlDrillsForChapter(chapter, pearlCards = []) {
  return pearlCards.filter(p => p.chapterId === chapter.id).map((p, i) => ({
    id: p.id,
    section: 'Clinical pearl',
    row: 'Recall this board pearl',
    column: p.front.slice(0, 140) + (p.front.length > 140 ? '…' : ''),
    answer: p.front,
    table: { headers: ['Pearl'], rows: [[p.front]] },
    pearl: true,
  }))
}

export default function Workbook({ guide, store, update, pearlCards = [], pdfLists = [] }) {
  const [chapterId, setChapterId] = useState(null)
  const chapter = guide.chapters.find(c => c.id === chapterId)
  const wb = store.workbook || {}

  if (!chapter) return (
    <div>
      <div className="manual-hero compact">
        <div>
          <p className="eyebrow">Active-recall workbooks</p>
          <h1>A workbook for every chapter</h1>
          <p>Reading is not studying. Each workbook turns the manual's tables, clinical pearls, and criteria into fill-in drills, adds case studies with model answers, and keeps your notes in one place. Print any chapter as a worksheet with an answer key.</p>
        </div>
        <div className="source-proof">
          <span><strong>{guide.chapters.reduce((a, c) => a + listDrills(c, pdfLists).length + tableDrills(c).length + pearlDrillsForChapter(c, pearlCards).length, 0).toLocaleString()}</strong> recall drills</span>
          <span><strong>{guide.chapters.reduce((a, c) => a + caseStudies(c).length, 0)}</strong> case studies</span>
          <span><strong>{guide.chapters.reduce((a, c) => a + chapterTables(c).length, 0)}</strong> clinical tables</span>
        </div>
      </div>
      <div className="section-title"><div><p className="eyebrow">Choose a chapter</p><h2>Workbooks</h2></div></div>
      <div className="manual-grid">
        {guide.chapters.map(c => {
          const drills = listDrills(c, pdfLists).length + tableDrills(c).length + pearlDrillsForChapter(c, pearlCards).length
          const doneN = Math.min(drills, Object.keys(wb[c.id]?.drills || {}).length)
          const right = Object.values(wb[c.id]?.drills || {}).filter(Boolean).length
          return (
            <article key={c.id} className="manual-card workbook-card" onClick={() => setChapterId(c.id)}>
              <div className="manual-number">{c.number}</div>
              <div><h3>{c.shortTitle}</h3><p>{listDrills(c, pdfLists).length + tableDrills(c).length + pearlDrillsForChapter(c, pearlCards).length} drills · {caseStudies(c).length} cases · {chapterTables(c).length} tables</p></div>
              <div className="wb-progress">
                <div className="bar"><i style={{ width: `${drills ? doneN / drills * 100 : 0}%` }} /></div>
                <span className="small muted">{drills ? `${doneN}/${drills} done${doneN ? ` · ${Math.round(right / doneN * 100)}% recalled` : ''}` : 'Notes and print worksheet'}</span>
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )

  return <ChapterWorkbook chapter={chapter} store={store} update={update} pearlCards={pearlCards} pdfLists={pdfLists} onBack={() => setChapterId(null)} />
}

function ChapterWorkbook({ chapter, store, update, pearlCards, pdfLists = [], onBack }) {
  const drills = useMemo(
    () => [...listDrills(chapter, pdfLists), ...tableDrills(chapter), ...pearlDrillsForChapter(chapter, pearlCards)],
    [chapter, pearlCards, pdfLists],
  )
  const cases = useMemo(() => caseStudies(chapter), [chapter])
  const tables = useMemo(() => chapterTables(chapter), [chapter])
  const [tab, setTab] = useState(drills.length ? 'drills' : cases.length ? 'cases' : 'notes')
  const state = (store.workbook || {})[chapter.id] || {}
  const results = state.drills || {}

  const [order, setOrder] = useState(() => shuffle(drills.map((_, i) => i)))
  const [pos, setPos] = useState(0)
  const [typed, setTyped] = useState('')
  const [shown, setShown] = useState(false)
  const remaining = order.filter(i => !(drills[i].id in results))
  const current = drills[order[pos % Math.max(1, order.length)]]

  function save(patch) {
    update(s => ({ ...s, workbook: { ...(s.workbook || {}), [chapter.id]: { ...((s.workbook || {})[chapter.id] || {}), ...patch(((s.workbook || {})[chapter.id] || {})) } } }))
  }
  function rate(ok) {
    save(st => ({ drills: { ...(st.drills || {}), [current.id]: ok } }))
    update(s => bumpDaily(s, 'cards', 1))
    setTyped(''); setShown(false); setPos(p => p + 1)
  }

  const doneN = Object.keys(results).length
  const right = Object.values(results).filter(Boolean).length

  return (
    <div className="workbook">
      <div className="no-print" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'space-between' }}>
        <button className="btn ghost" onClick={onBack}><ArrowLeft size={17} /> All workbooks</button>
        <button className="btn ghost" onClick={() => { setTab('print'); setTimeout(() => window.print(), 150) }}><Printer size={17} /> Print worksheet + answer key</button>
      </div>
      <div className="manual-head no-print">
        <div><p className="label">Chapter {chapter.number} workbook</p><h1>{chapter.shortTitle}</h1>
          <p className="muted">{doneN}/{drills.length} drills done{doneN ? ` · ${Math.round(right / doneN * 100)}% recalled correctly` : ''} · {cases.length} case studies</p></div>
      </div>
      <div className="segmented no-print" role="tablist">
        {drills.length > 0 && <button type="button" className={tab === 'drills' ? 'active' : ''} onClick={() => setTab('drills')}><Grid3x3 size={16} /> Recall drills</button>}
        {cases.length > 0 && <button type="button" className={tab === 'cases' ? 'active' : ''} onClick={() => setTab('cases')}><Stethoscope size={16} /> Case studies</button>}
        <button type="button" className={tab === 'notes' ? 'active' : ''} onClick={() => setTab('notes')}><NotebookPen size={16} /> My notes</button>
        <button type="button" className={tab === 'print' ? 'active' : ''} onClick={() => setTab('print')}><PencilLine size={16} /> Worksheet</button>
      </div>

      {tab === 'drills' && current && (
        <div className="drill-card card">
          <p className="label">{current.section} · drill {(pos % order.length) + 1} of {order.length} · {remaining.length} not yet attempted</p>
          <p className="drill-row">{current.row}</p>
          <p className="drill-col">{current.column}?</p>
          {!shown ? <>
            <textarea className="drill-input" value={typed} onChange={e => setTyped(e.target.value)} placeholder="Type your answer from memory, then reveal…" rows={2}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); setShown(true) } }} />
            <button className="btn" onClick={() => setShown(true)}><Eye size={16} /> Reveal answer</button>
          </> : <>
            {typed && <p className="small muted">Your answer: <em>{typed}</em></p>}
            {current.kind === 'list'
              ? <ol className="drill-list">{current.items.map((it, k) => <li key={k}>{it}</li>)}</ol>
              : <div className="drill-answer">{current.answer}</div>}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button className="btn ghost" onClick={() => rate(false)}><X size={16} /> Missed it</button>
              <button className="btn" onClick={() => rate(true)}><Check size={16} /> Got it</button>
            </div>
          </>}
          <div className="drill-foot">
            <button className="linkbtn" onClick={() => { setOrder(shuffle(drills.map((_, i) => i))); setPos(0); setShown(false); setTyped('') }}>Shuffle</button>
            <button className="linkbtn" onClick={() => { const missed = drills.map((d, i) => results[d.id] === false ? i : -1).filter(i => i >= 0); if (missed.length) { setOrder(missed); setPos(0); setShown(false) } }}>Drill only missed ({Object.values(results).filter(v => v === false).length})</button>
            <button className="linkbtn" onClick={() => { if (confirm('Reset drill progress for this chapter?')) save(() => ({ drills: {} })) }}>Reset</button>
          </div>
          <details className="drill-context"><summary>Show the full source table</summary>
            <div className="tablewrap"><table><thead><tr>{current.table.headers.map((h, j) => <th key={j}>{h}</th>)}</tr></thead>
              <tbody>{current.table.rows.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{c}</td>)}</tr>)}</tbody></table></div>
          </details>
        </div>
      )}

      {tab === 'cases' && (
        <div>
          <p className="muted">Work each case like the exam: commit to a diagnosis and next step in writing, then compare with the model answer.</p>
          {cases.map((q, i) => <CaseStudy key={q.id} q={q} i={i} saved={(state.cases || {})[q.id] || ''} onSave={v => save(st => ({ cases: { ...(st.cases || {}), [q.id]: v } }))} />)}
        </div>
      )}

      {tab === 'notes' && (
        <div className="card">
          <p className="label">My notes: {chapter.shortTitle}</p>
          <textarea className="notes-area" defaultValue={state.notes || ''} placeholder="Mnemonics, weak spots, things your instructor emphasized… Saved automatically on this device."
            onBlur={e => save(() => ({ notes: e.target.value }))} rows={14} />
          <p className="small muted">Saved when you click away. Included in progress export.</p>
        </div>
      )}

      {tab === 'print' && (
        <div className="worksheet">
          <h1>{chapter.shortTitle}: Workbook</h1>
          <p className="muted">APEA 2026 FNP Study Hub · Name: ____________________ · Date: __________</p>
          <h2>Part A: Complete the tables</h2>
          {tables.map((t, i) => (
            <div key={i} className="ws-table"><p className="label">{t.section}</p>
              <table><thead><tr>{t.headers.map((h, j) => <th key={j}>{h}</th>)}</tr></thead>
                <tbody>{t.rows.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{k === 0 ? c : <span className="blank">&nbsp;</span>}</td>)}</tr>)}</tbody></table></div>
          ))}
          {cases.length > 0 && <><h2>Part B: Case studies</h2>
            {cases.map((q, i) => <div key={q.id} className="ws-case"><p><strong>{i + 1}.</strong> {q.stem}</p><div className="ws-lines" /></div>)}</>}
          <div className="page-break" />
          <h2>Answer key</h2>
          {tables.map((t, i) => (
            <div key={i} className="ws-table"><p className="label">{t.section}</p>
              <table><thead><tr>{t.headers.map((h, j) => <th key={j}>{h}</th>)}</tr></thead>
                <tbody>{t.rows.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{c}</td>)}</tr>)}</tbody></table></div>
          ))}
          {cases.map((q, i) => <p key={q.id} className="small"><strong>Case {i + 1}:</strong> {q.explanation}</p>)}
        </div>
      )}
    </div>
  )
}

function CaseStudy({ q, i, saved, onSave }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="card case-card">
      <p className="label">Case {i + 1}</p>
      <p className="case-stem">{q.stem}</p>
      <textarea className="drill-input" defaultValue={saved} rows={3} placeholder="Your assessment and plan…" onBlur={e => onSave(e.target.value)} />
      {!open ? <button className="btn ghost" onClick={() => setOpen(true)}><Eye size={16} /> Show model answer</button>
        : <div className="drill-answer"><strong>Model answer:</strong> {q.explanation}</div>}
    </div>
  )
}
