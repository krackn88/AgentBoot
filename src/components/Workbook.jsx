import React, { useMemo, useState } from 'react'
import { ArrowLeft, Printer, PencilLine, Grid3x3, Stethoscope, NotebookPen, Eye, Check, X, BookOpen, Brain, Lightbulb, Target } from 'lucide-react'
import { bumpDaily, shuffle } from '../lib/store'
import { drillsFromTable, tableIsDrillable, topicPhrase, splitTopic, clozeFrom, pearlPrompt, answerWithWhy } from '../lib/drills'
import { guidedWorkbookFor } from '../lib/guidedWorkbook'

/**
 * Every drill exposes the same shape the card renders:
 *   prompt - a question a clinician would actually ask
 *   answer - the expected response (a string, or `items` for a list)
 * Anything that cannot be phrased as a question is not surfaced.
 */
function tableDrills(chapter) {
  const out = []
  chapter.sections.forEach(s => (s.blocks || []).forEach((b, bi) => {
    if (b.type !== 'table' || !tableIsDrillable(b)) return
    drillsFromTable(b, { section: s.title, tableKey: `${s.id}-t${bi}` }).forEach(d => {
      out.push({
        id: d.id,
        section: s.title,
        prompt: d.prompt,
        answer: d.answer,
        kind: 'table',
        table: b,
      })
    })
  }))
  return out
}

function caseStudies(chapter) {
  return (chapter.questions || []).filter(q =>
    q.stem &&
    Array.isArray(q.options) &&
    q.options.length >= 2 &&
    Number.isInteger(q.correctIndex) &&
    q.correctIndex >= 0 &&
    q.correctIndex < q.options.length,
  )
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
    .filter(l => l.chapterId === chapter.id && l.items?.length >= 3 && l.prompt)
    .map(l => ({
      id: l.id,
      section: l.section || chapter.shortTitle,
      prompt: l.prompt,
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

/**
 * Pearl drills: turn each pearl into a question rather than showing it to reveal
 * itself. The pearl is a statement about a topic, so the prompt names the topic and
 * the answer is the statement.
 */
function pearlDrillsForChapter(chapter, pearlCards = []) {
  return pearlCards
    .filter(p => p.chapterId === chapter.id && p.front && p.front.length > 30)
    .flatMap(p => {
      const text = p.front.trim()
      const { topic } = splitTopic(text)
      const base = { id: p.id, section: p.tag || 'Clinical pearl', kind: 'pearl' }
      if (topic) return [{ ...base, prompt: pearlPrompt(topic), answer: text }]
      const cloze = clozeFrom(text)
      if (!cloze) return []
      return [{ ...base, prompt: cloze.prompt, answer: `${cloze.answer} — ${cloze.full}` }]
    })
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
          <p>Learn the concept, classify the pattern, then make the clinical call. Each chapter pairs guided writing prompts with source tables and real board-style questions. Print any chapter as a worksheet with its answer key.</p>
        </div>
        <div className="source-proof">
          <span><strong>{guide.chapters.reduce((a, c) => a + listDrills(c, pdfLists).length + tableDrills(c).length + pearlDrillsForChapter(c, pearlCards).length, 0).toLocaleString()}</strong> recall drills</span>
          <span><strong>{guide.chapters.reduce((a, c) => a + caseStudies(c).length, 0)}</strong> board questions</span>
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
              <div><h3>{c.shortTitle}</h3><p>guided lesson · {caseStudies(c).length} board questions · {listDrills(c, pdfLists).length + tableDrills(c).length} recall drills</p></div>
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

export function ChapterWorkbook({ chapter, store, update, pearlCards, pdfLists = [], onBack }) {
  const drills = useMemo(
    () => [...listDrills(chapter, pdfLists), ...tableDrills(chapter), ...pearlDrillsForChapter(chapter, pearlCards)],
    [chapter, pearlCards, pdfLists],
  )
  const cases = useMemo(() => caseStudies(chapter), [chapter])
  const tables = useMemo(() => chapterTables(chapter), [chapter])
  const guided = useMemo(() => guidedWorkbookFor(chapter), [chapter])
  const [tab, setTab] = useState('guided')
  const state = (store.workbook || {})[chapter.id] || {}
  const results = state.drills || {}

  const [order, setOrder] = useState(() => shuffle(drills.map((_, i) => i)))
  const [pos, setPos] = useState(0)
  const [typed, setTyped] = useState('')
  const [shown, setShown] = useState(false)
  const remaining = order.filter(i => drills[i] && !(drills[i].id in results))
  const current = drills[order[pos % Math.max(1, order.length)]]

  // Guard against a stale order array (e.g. after the chapter's drills change):
  // indexing past the end used to throw while rendering.
  const active = current && current.id ? current : drills[0]

  function save(patch) {
    update(s => ({ ...s, workbook: { ...(s.workbook || {}), [chapter.id]: { ...((s.workbook || {})[chapter.id] || {}), ...patch(((s.workbook || {})[chapter.id] || {})) } } }))
  }
  function rate(ok) {
    save(st => ({ drills: { ...(st.drills || {}), [active.id]: ok } }))
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
          <p className="muted">{doneN}/{drills.length} drills done{doneN ? ` · ${Math.round(right / doneN * 100)}% recalled correctly` : ''} · {cases.length} board questions</p></div>
      </div>
      <div className="segmented no-print" role="tablist">
        <button type="button" className={tab === 'guided' ? 'active' : ''} onClick={() => setTab('guided')}><BookOpen size={16} /> Guided workbook</button>
        {drills.length > 0 && <button type="button" className={tab === 'drills' ? 'active' : ''} onClick={() => setTab('drills')}><Grid3x3 size={16} /> Recall drills</button>}
        {cases.length > 0 && <button type="button" className={tab === 'cases' ? 'active' : ''} onClick={() => setTab('cases')}><Stethoscope size={16} /> Board questions</button>}
        <button type="button" className={tab === 'notes' ? 'active' : ''} onClick={() => setTab('notes')}><NotebookPen size={16} /> My notes</button>
        <button type="button" className={tab === 'print' ? 'active' : ''} onClick={() => setTab('print')}><PencilLine size={16} /> Worksheet</button>
      </div>

      {tab === 'guided' && (
        <GuidedWorkbook
          guide={guided}
          cases={cases}
          saved={state.guided || {}}
          onSave={(id, value) => save(st => ({ guided: { ...(st.guided || {}), [id]: value } }))}
        />
      )}

      {tab === 'drills' && active && (
        <div className="drill-card card">
          <p className="label">
            {active.section} · drill {(pos % order.length) + 1} of {order.length}
            {remaining.length > 0 && ` · ${remaining.length} not yet attempted`}
          </p>
          <p className="drill-question">{active.prompt}</p>
          {active.kind === 'list' && (
            <p className="drill-cue">Recall all {active.items.length} items.</p>
          )}
          {!shown ? (
            <>
              <textarea
                className="drill-input"
                value={typed}
                onChange={e => setTyped(e.target.value)}
                placeholder="Answer from memory, then reveal…"
                rows={active.kind === 'list' ? 4 : 3}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    setShown(true)
                  }
                }}
              />
              <button className="btn" onClick={() => setShown(true)}><Eye size={16} /> Reveal answer</button>
            </>
          ) : (
            <>
              {typed && <p className="small muted">Your answer: <em>{typed}</em></p>}
              <p className="drill-answer-label">Answer</p>
              {active.kind === 'list'
                ? <ol className="drill-list">{active.items.map((it, k) => <li key={k}>{it}</li>)}</ol>
                : <div className="drill-answer">{active.answer}</div>}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button className="btn ghost" onClick={() => rate(false)}><X size={16} /> Missed it</button>
                <button className="btn" onClick={() => rate(true)}><Check size={16} /> Got it</button>
              </div>
            </>
          )}
          <div className="drill-foot">
            <button className="linkbtn" onClick={() => { setOrder(shuffle(drills.map((_, i) => i))); setPos(0); setShown(false); setTyped('') }}>Shuffle</button>
            <button className="linkbtn" onClick={() => { const missed = drills.map((d, i) => results[d.id] === false ? i : -1).filter(i => i >= 0); if (missed.length) { setOrder(missed); setPos(0); setShown(false) } }}>Drill only missed ({Object.values(results).filter(v => v === false).length})</button>
            <button className="linkbtn" onClick={() => { if (confirm('Reset drill progress for this chapter?')) save(() => ({ drills: {} })) }}>Reset</button>
          </div>
          {active.kind === 'list' ? (
            <div className="drill-context">
              <p className="drill-context-title">Full list{active.page != null ? ` · source page ${active.page + 1}` : ''}</p>
              <ol className="drill-list">{active.items.map((it, k) => <li key={k}>{it}</li>)}</ol>
            </div>
          ) : active.table?.headers?.length ? (
            <div className="drill-context">
              <p className="drill-context-title">Full source table</p>
              <div className="tablewrap">
                <table>
                  <thead><tr>{active.table.headers.map((h, j) => <th key={j}>{h}</th>)}</tr></thead>
                  <tbody>{active.table.rows.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{c}</td>)}</tr>)}</tbody>
                </table>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {tab === 'cases' && (
        <div>
          <div className="workbook-instruction">
            <Target size={20} />
            <p><strong>Commit before you reveal.</strong> Identify the diagnosis, next best step, or treatment in your own words. Then choose an option and compare your reasoning with the answer.</p>
          </div>
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
          {guided.concepts?.length > 0 && <><h2>Part A: Build the concept</h2>
            {guided.concepts.map((item, i) => <div key={i} className="ws-case"><p><strong>{i + 1}.</strong> {item.prompt}</p><div className="ws-lines" /></div>)}
          </>}
          {cases.length > 0 && <><h2>Part B: Board-style clinical reasoning</h2>
            {cases.map((q, i) => <div key={q.id} className="ws-case"><p><strong>{i + 1}.</strong> {q.stem}</p><div className="ws-lines" /></div>)}</>}
          <div className="page-break" />
          <h2>Answer key</h2>
          {guided.concepts?.map((item, i) => <p key={`concept-${i}`} className="small"><strong>Concept {i + 1}:</strong> {item.answer}</p>)}
          {tables.map((t, i) => (
            <div key={i} className="ws-table"><p className="label">{t.section}</p>
              <table><thead><tr>{t.headers.map((h, j) => <th key={j}>{h}</th>)}</tr></thead>
                <tbody>{t.rows.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{c}</td>)}</tr>)}</tbody></table></div>
          ))}
          {cases.map((q, i) => <p key={q.id} className="small"><strong>Case {i + 1}:</strong> {answerWithWhy(q.options[q.correctIndex], q.explanation)}</p>)}
        </div>
      )}
    </div>
  )
}

function GuidedWorkbook({ guide, cases, saved, onSave }) {
  const featuredCases = cases.slice(0, 4)
  return (
    <div className="guided-workbook">
      <section className="workbook-cover">
        <div>
          <p className="eyebrow">Clinical learning sequence</p>
          <h2>{guide.title}</h2>
          <p>{guide.subtitle}</p>
        </div>
        <div className="workbook-cover-mark"><Brain size={28} /><span>Learn it.<br />Use it.</span></div>
      </section>

      <section className="workbook-section">
        <StepHeading number="1" kicker="Build the concept" title="Know what each finding means" />
        <div className="objective-strip">
          {guide.objectives.map((objective, i) => <div key={i}><Check size={15} /><span>{objective}</span></div>)}
        </div>
        <div className="guided-prompt-grid">
          {guide.concepts.map((item, i) => (
            <WorkbookPrompt
              key={i}
              number={i + 1}
              item={item}
              saved={saved[`concept-${i}`] || ''}
              onSave={value => onSave(`concept-${i}`, value)}
            />
          ))}
        </div>
      </section>

      {guide.matrix && (
        <section className="workbook-section">
          <StepHeading number="2" kicker="Classify & compare" title={guide.matrix.title || 'Build the pattern'} />
          <p className="workbook-directions">Cover the right-hand columns. For each condition or finding, predict the pattern and the FNP action before checking the row.</p>
          <div className="pattern-table-wrap">
            <table className="pattern-table">
              <thead><tr>{guide.matrix.headers.map((header, i) => <th key={i}>{header}</th>)}</tr></thead>
              <tbody>{guide.matrix.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j} className={j === 0 ? 'pattern-name' : ''}>{cell}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </section>
      )}

      {guide.patternChecks?.length > 0 && (
        <section className="workbook-section">
          <StepHeading number="3" kicker="Pattern recognition" title="Read the data, then make the call" />
          <div className="pattern-check-grid">
            {guide.patternChecks.map((item, i) => (
              <WorkbookPrompt
                key={i}
                number={i + 1}
                item={{ ...item, prompt: `${item.data}\n${item.prompt}` }}
                label={item.label}
                saved={saved[`pattern-${i}`] || ''}
                onSave={value => onSave(`pattern-${i}`, value)}
              />
            ))}
          </div>
        </section>
      )}

      {featuredCases.length > 0 && (
        <section className="workbook-section">
          <StepHeading number={guide.patternChecks?.length ? '4' : '3'} kicker="Clinical application" title="Work real board-style questions" />
          <p className="workbook-directions">These are chapter questions—not generated trivia. State the diagnosis or next step before opening the answer.</p>
          {featuredCases.map((q, i) => <CaseStudy key={q.id} q={q} i={i} compact />)}
        </section>
      )}

      {guide.pearls?.length > 0 && (
        <section className="workbook-section board-pearl-panel">
          <StepHeading number="★" kicker="Board pearls" title="Do not leave the chapter without these" />
          <div className="board-pearl-grid">
            {guide.pearls.map((pearl, i) => <div key={i}><Lightbulb size={18} /><p>{pearl}</p></div>)}
          </div>
        </section>
      )}
    </div>
  )
}

function StepHeading({ number, kicker, title }) {
  return (
    <div className="step-heading">
      <span>{number}</span>
      <div><p>{kicker}</p><h3>{title}</h3></div>
    </div>
  )
}

function WorkbookPrompt({ item, number, label, saved = '', onSave }) {
  const [open, setOpen] = useState(false)
  return (
    <article className="guided-prompt">
      <p className="guided-prompt-label">{label || `Question ${number}`}</p>
      <p className="guided-prompt-question">{item.prompt}</p>
      <textarea
        className="workbook-line-input"
        defaultValue={saved}
        aria-label={`Your answer to ${item.prompt}`}
        placeholder="Write your answer…"
        rows={3}
        onBlur={e => onSave?.(e.target.value)}
      />
      <button type="button" className="answer-toggle" onClick={() => setOpen(value => !value)}>
        <Eye size={15} /> {open ? 'Hide answer' : 'Check answer'}
      </button>
      {open && <div className="guided-answer"><strong>Expected answer</strong><p>{item.answer}</p></div>}
    </article>
  )
}

function CaseStudy({ q, i, saved, onSave }) {
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState(null)
  const answer = q.options?.[q.correctIndex]
  return (
    <div className="card case-card">
      <p className="label">Board question {i + 1}</p>
      <p className="case-stem">{q.stem}</p>
      {!open && !saved && <textarea className="drill-input" rows={2} placeholder="Your diagnosis, reasoning, or next step…" onBlur={e => onSave?.(e.target.value)} />}
      {saved && <p className="case-written"><strong>Your written answer:</strong> {saved}</p>}
      <div className="case-options">
        {q.options?.map((option, index) => (
          <button
            type="button"
            key={index}
            className={`case-option ${selected === index ? 'selected' : ''} ${open && index === q.correctIndex ? 'correct' : ''} ${open && selected === index && index !== q.correctIndex ? 'incorrect' : ''}`}
            onClick={() => !open && setSelected(index)}
          >
            <span>{String.fromCharCode(65 + index)}</span>{option}
          </button>
        ))}
      </div>
      {!open ? <button className="btn ghost" onClick={() => setOpen(true)}><Eye size={16} /> Reveal answer & rationale</button>
        : <div className="drill-answer"><strong>{answer}</strong><p>{q.explanation || 'Use the chapter source to review this answer.'}</p></div>}
    </div>
  )
}
