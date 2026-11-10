import React, { useEffect, useMemo, useState } from 'react'
import { Printer, BookOpen, Star, Eye, EyeOff, GraduationCap, PenLine, Lightbulb, Target, ListChecks } from 'lucide-react'
import { guidedWorkbookFor, curatedChapterIds } from '../lib/guidedWorkbook'
import { answerWithWhy } from '../lib/drills'

const CURATED = new Set(curatedChapterIds())

function validQuestions(chapter) {
  return (chapter.questions || []).filter(q =>
    q.stem && Array.isArray(q.options) && q.options.length >= 2 &&
    Number.isInteger(q.correctIndex) && q.correctIndex >= 0 && q.correctIndex < q.options.length)
}

export default function FnpWorkbook({ guide, store, update }) {
  const chapters = useMemo(() => guide.chapters.filter(c => validQuestions(c).length > 0), [guide])
  const [chapterId, setChapterId] = useState('hematology')
  const [scope, setScope] = useState('chapter')
  const [coverAnswers, setCoverAnswers] = useState(true)
  const [printMode, setPrintMode] = useState('both')
  const chapter = chapters.find(c => c.id === chapterId) || chapters[0]
  const activeChapters = scope === 'full' ? chapters : [chapter]

  useEffect(() => {
    document.body.classList.add('fnp-wb-active')
    return () => document.body.classList.remove('fnp-wb-active')
  }, [])

  function printWith(mode) {
    setPrintMode(mode)
    requestAnimationFrame(() => requestAnimationFrame(() => window.print()))
  }

  const lessonPages = activeChapters.length * 5
  const totalPages = lessonPages + activeChapters.length + 3

  return (
    <div className={`fnp-wb-root print-${printMode}`}>
      <div className="wb-toolbar no-print">
        <div>
          <p className="eyebrow">The print-first companion</p>
          <h1 className="wb-toolbar-title">The FNP Workbook</h1>
          <p className="muted" style={{ margin: '4px 0 0', maxWidth: 560, lineHeight: 1.55 }}>
            A workbook you can study on screen or print and write in — concept cards, classification tables,
            pattern cases, board questions, and a full answer key. Built to become the sellable print edition.
          </p>
        </div>
        <div className="wb-toolbar-actions">
          <label className="wb-field">Workbook
            <select value={scope} onChange={e => setScope(e.target.value)}>
              <option value="chapter">One chapter</option>
              <option value="full">Full workbook (all chapters)</option>
            </select>
          </label>
          {scope === 'chapter' && (
            <label className="wb-field">Chapter
              <select value={chapter?.id} onChange={e => setChapterId(e.target.value)}>
                {chapters.map(c => <option key={c.id} value={c.id}>{c.number}. {c.shortTitle}{CURATED.has(c.id) ? ' ★' : ''}</option>)}
              </select>
            </label>
          )}
          <div className="wb-toolbar-buttons">
            <button type="button" className="btn ghost" onClick={() => setCoverAnswers(v => !v)}>
              {coverAnswers ? <EyeOff size={16} /> : <Eye size={16} />} {coverAnswers ? 'Cover answers' : 'Show answers'}
            </button>
            <button type="button" className="btn ghost" onClick={() => printWith('workbook')}><Printer size={16} /> Print workbook</button>
            <button type="button" className="btn ghost" onClick={() => printWith('key')}><ListChecks size={16} /> Print answer key</button>
            <button type="button" className="btn" onClick={() => printWith('both')}><BookOpen size={16} /> Print everything</button>
          </div>
          <p className="small muted" style={{ margin: 0 }}>★ = hand-built lesson · about {totalPages} pages in this selection. In the print dialog choose “Save as PDF”, Letter, and background graphics on.</p>
        </div>
      </div>

      <CoverPage scope={scope} chapter={chapter} chapters={chapters} />
      <ContentsPage chapters={chapters} onPick={(id) => { setChapterId(id); setScope('chapter'); window.scrollTo(0, 0) }} />

      {activeChapters.map(c => (
        <LessonPages
          key={c.id}
          chapter={c}
          store={store}
          update={update}
          coverAnswers={coverAnswers}
        />
      ))}

      <section className="wb-page wb-key-intro">
        <p className="wb-kicker">Back of book</p>
        <h2 className="wb-page-title">Answer Key &amp; Rationales</h2>
        <p className="wb-lede">Cover this section while you work. Every concept check, pattern case, and board question is answered here with the reasoning — not just the letter.</p>
        <div className="wb-howto">
          <div><strong>1</strong><span>Commit in pencil first. A circled guess teaches more than a peeked answer.</span></div>
          <div><strong>2</strong><span>Check and annotate. Write <em>why</em> the right answer wins in the margin.</span></div>
          <div><strong>3</strong><span>Star what you missed and log it on the tracker page.</span></div>
        </div>
      </section>

      {activeChapters.map(c => <AnswerKeyPage key={`key-${c.id}`} chapter={c} />)}
      <TrackerPage chapters={chapters} />
    </div>
  )
}

function CoverPage({ scope, chapter, chapters }) {
  return (
    <section className="wb-page wb-cover">
      <div className="wb-cover-top">
        <span className="wb-edition">2026 Edition · FNP / AGPCNP</span>
        <span className="wb-cover-star"><GraduationCap size={18} /> Board-success series</span>
      </div>
      <p className="wb-cover-kicker">The clinical reasoning workbook</p>
      <h2 className="wb-cover-title">The FNP<br />Workbook</h2>
      <p className="wb-cover-sub">Decode the numbers · Classify the pattern · Make the call</p>
      <p className="wb-cover-desc">
        {scope === 'full'
          ? `The complete workbook: ${chapters.length} chapter lessons that turn board content into handwriting, pattern recognition, and clinical decisions.`
          : `Chapter lesson: ${chapter.shortTitle}. Switch to the full workbook above to print every chapter as one bound book.`}
      </p>
      <div className="wb-cover-lines">
        <p><span>Name</span><i /></p>
        <p><span>Program / cohort</span><i /></p>
        <p><span>Exam date</span><i /></p>
      </div>
      <div className="wb-cover-inside">
        <p className="label">Inside every lesson</p>
        <ul>
          <li>Build the Concept — the terms and numbers, decoded</li>
          <li>Classify It — comparison tables you complete from memory</li>
          <li>Pattern Cases — real data, real decisions</li>
          <li>Board Questions — keyed answers with rationales in the back</li>
          <li>Board Pearls — the lines worth memorizing cold</li>
        </ul>
      </div>
      <p className="wb-cover-foot">For personal study use. Educational content only — not a substitute for current clinical guidelines or your program&apos;s materials.</p>
    </section>
  )
}

function ContentsPage({ chapters, onPick }) {
  return (
    <section className="wb-page wb-contents">
      <p className="wb-kicker">Contents</p>
      <h2 className="wb-page-title">How this workbook works</h2>
      <div className="wb-howto">
        <div><strong>1</strong><span><b>Build it.</b> Learn what each number and term actually means before touching questions.</span></div>
        <div><strong>2</strong><span><b>Classify it.</b> Complete the comparison table from memory, then check yourself.</span></div>
        <div><strong>3</strong><span><b>Use it.</b> Work the pattern cases and board questions, then read every rationale.</span></div>
      </div>
      <div className="wb-toc">
        {chapters.map(c => (
          <button type="button" key={c.id} className="wb-toc-row no-print-btn" onClick={() => onPick(c.id)}>
            <span className="wb-toc-num">{c.number}</span>
            <span className="wb-toc-name">{c.shortTitle}</span>
            {CURATED.has(c.id) && <span className="wb-toc-star"><Star size={13} /> curated lesson</span>}
            <span className="wb-toc-meta">{validQuestions(c).length} board questions</span>
          </button>
        ))}
      </div>
      <p className="small muted">★ Curated lessons are hand-built (concept cards, comparison matrix, pattern cases). Every other chapter follows the same five-page lesson built from its source tables and keyed questions.</p>
    </section>
  )
}

function PageShell({ chapter, label, children, tone }) {
  return (
    <section className={`wb-page wb-lesson ${tone || ''}`}>
      <header className="wb-lesson-head">
        <span className="wb-lesson-num">{chapter.number}</span>
        <div>
          <p>{chapter.shortTitle}</p>
          <h3>{label}</h3>
        </div>
      </header>
      {children}
      <footer className="wb-foot"><span>The FNP Workbook · {chapter.shortTitle}</span><span>Knowledge today. Better care tomorrow.</span></footer>
    </section>
  )
}

function LessonPages({ chapter, store, update, coverAnswers }) {
  const g = guidedWorkbookFor(chapter)
  const questions = validQuestions(chapter)
  const miniCase = questions[0]
  const boardQs = questions.slice(1, 6)
  const saved = (store.fnpWorkbook || {})[chapter.id] || {}

  function save(id, value) {
    update(s => ({
      ...s,
      fnpWorkbook: {
        ...(s.fnpWorkbook || {}),
        [chapter.id]: { ...((s.fnpWorkbook || {})[chapter.id] || {}), [id]: value },
      },
    }))
  }

  return (
    <>
      <PageShell chapter={chapter} label={g.title}>
        <p className="wb-tagline">{g.subtitle}</p>
        <div className="wb-objectives">
          {g.objectives.map((o, i) => <p key={i}><span className="wb-check" />{o}</p>)}
        </div>
        <p className="wb-section-label"><span>1</span> Build the concept</p>
        {g.conceptCards ? (
          <div className="wb-concept-grid">
            {g.conceptCards.map((card, i) => (
              <article key={i} className="wb-concept-card">
                <h4>{card.term}</h4>
                <p className="wb-concept-what">{card.measures}</p>
                <p className="wb-concept-range">{card.normal}</p>
                <p className="wb-concept-clue">{card.clue}</p>
                <WriteLines id={`card-${i}`} saved={saved} save={save} small />
              </article>
            ))}
          </div>
        ) : (
          <div className="wb-prompt-grid">
            {g.concepts.slice(0, 4).map((item, i) => (
              <WritePrompt key={i} n={i + 1} item={item} id={`concept-${i}`} saved={saved} save={save} />
            ))}
          </div>
        )}
      </PageShell>

      <PageShell chapter={chapter} label="Classify it & spot the pattern" tone="tone-teal">
        {g.matrix && (
          <>
            <p className="wb-section-label"><span>2</span> {g.matrix.title || 'Classify it'}</p>
            <p className="wb-directions">Complete each row from memory. {coverAnswers ? 'Answers are covered — check the key in the back.' : 'Answers shown for review.'}</p>
            <table className={`wb-matrix ${coverAnswers ? 'covered' : ''}`}>
              <thead><tr>{g.matrix.headers.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
              <tbody>
                {g.matrix.rows.map((row, i) => (
                  <tr key={i}>{row.map((cell, j) => (
                    <td key={j} className={j === 0 ? 'wb-matrix-name' : ''}>
                      {j === 0 ? cell : <><span className="cell-answer">{cell}</span><span className="cell-lines" /></>}
                    </td>
                  ))}</tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {g.patternChecks?.length > 0 && (
          <>
            <p className="wb-section-label"><span>3</span> What suggests what?</p>
            <div className="wb-prompt-grid">
              {g.patternChecks.map((item, i) => (
                <WritePrompt key={i} n={i + 1} item={{ prompt: `${item.data} — ${item.prompt}` }} label={item.label} id={`pattern-${i}`} saved={saved} save={save} />
              ))}
            </div>
          </>
        )}
        {!g.matrix && !g.patternChecks?.length && (
          <>
            <p className="wb-section-label"><span>2</span> Build your own comparison</p>
            <p className="wb-directions">Use the chapter&apos;s reference tables in the study guide to complete this grid for the conditions you confuse most.</p>
            <table className="wb-matrix covered">
              <thead><tr><th>Condition</th><th>Signature clues</th><th>Key test</th><th>First move</th></tr></thead>
              <tbody>{[0, 1, 2, 3].map(i => <tr key={i}><td><span className="cell-lines" /></td><td><span className="cell-lines" /></td><td><span className="cell-lines" /></td><td><span className="cell-lines" /></td></tr>)}</tbody>
            </table>
          </>
        )}
      </PageShell>

      <PageShell chapter={chapter} label="Check your understanding" tone="tone-gold">
        <p className="wb-section-label"><span>4</span> Answer in your own words</p>
        <div className="wb-prompt-list">
          {g.concepts.map((item, i) => (
            <WritePrompt key={i} n={i + 1} item={item} id={`check-${i}`} saved={saved} save={save} wide />
          ))}
        </div>
      </PageShell>

      <PageShell chapter={chapter} label="Mini case & board questions" tone="tone-coral">
        {miniCase && (
          <>
            <p className="wb-section-label"><span>5</span> Mini case</p>
            <article className="wb-mini-case">
              <p>{miniCase.stem}</p>
              <p className="wb-mini-q">Your diagnosis / next step, and why:</p>
              <WriteLines id="mini-case" saved={saved} save={save} rows={3} />
            </article>
          </>
        )}
        <p className="wb-section-label"><span>6</span> Board questions — circle your answer</p>
        <div className="wb-mcq-list">
          {boardQs.map((q, i) => (
            <ScreenQuestion key={q.id} q={q} n={i + 1} chapterId={chapter.id} saved={saved} save={save} />
          ))}
        </div>
      </PageShell>

      <PageShell chapter={chapter} label="Board pearls & confidence check" tone="tone-navy">
        <p className="wb-section-label"><span>★</span> Board pearls</p>
        {g.pearls?.length ? (
          <div className="wb-pearl-grid">
            {g.pearls.map((pearl, i) => <div key={i} className="wb-pearl"><Lightbulb size={16} /><p>{pearl}</p></div>)}
          </div>
        ) : (
          <div className="wb-pearl-empty">
            <p>Write the four lines from this chapter you would want taped above your desk:</p>
            <WriteLines id="my-pearls" saved={saved} save={save} rows={4} />
          </div>
        )}
        <p className="wb-section-label"><span>✓</span> Confidence check</p>
        <div className="wb-confidence">
          <p>Right now I could teach this chapter to a classmate:</p>
          <div className="wb-confidence-scale">{[1, 2, 3, 4, 5].map(n => <span key={n} className="wb-conf-dot">{n}</span>)}</div>
          <p className="wb-confidence-ends"><span>Not yet</span><span>Cold</span></p>
        </div>
        <p className="wb-mini-q"><PenLine size={14} /> One thing I will re-read before exam day:</p>
        <WriteLines id="reread" saved={saved} save={save} rows={2} />
        <p className="wb-mini-q"><Target size={14} /> My notes</p>
        <WriteLines id="notes" saved={saved} save={save} rows={5} />
      </PageShell>
    </>
  )
}

function WriteLines({ id, saved, save, rows = 2, small }) {
  return (
    <textarea
      className={`wb-lines-input ${small ? 'small' : ''}`}
      rows={rows}
      defaultValue={saved[id] || ''}
      placeholder="Write here…"
      aria-label="Workbook writing space"
      onBlur={e => save(id, e.target.value)}
    />
  )
}

function WritePrompt({ item, n, label, id, saved, save, wide }) {
  const [open, setOpen] = useState(false)
  return (
    <article className={`wb-prompt ${wide ? 'wide' : ''}`}>
      <p className="wb-prompt-label">{label || `Question ${n}`}</p>
      <p className="wb-prompt-q">{item.prompt}</p>
      <WriteLines id={id} saved={saved} save={save} rows={wide ? 3 : 2} />
      <button type="button" className="wb-reveal no-print" onClick={() => setOpen(v => !v)}>
        <Eye size={14} /> {open ? 'Hide expected answer' : 'Check expected answer'}
      </button>
      {open && <p className="wb-expected"><strong>Expected:</strong> {item.answer}</p>}
    </article>
  )
}

function ScreenQuestion({ q, n, saved, save }) {
  const key = `mcq-${q.id}`
  const picked = saved[key]
  const [revealed, setRevealed] = useState(false)
  return (
    <article className="wb-mcq">
      <p className="wb-mcq-stem"><strong>{n}.</strong> {q.stem}</p>
      <div className="wb-mcq-options">
        {q.options.map((option, i) => {
          const letter = String.fromCharCode(65 + i)
          const cls = [
            'wb-mcq-option',
            picked === i ? 'picked' : '',
            revealed && i === q.correctIndex ? 'correct' : '',
            revealed && picked === i && i !== q.correctIndex ? 'wrong' : '',
          ].join(' ')
          return (
            <button type="button" key={i} className={cls} onClick={() => { if (!revealed) save(key, i) }}>
              <span className="wb-mcq-letter">{letter}</span><span>{option}</span>
            </button>
          )
        })}
      </div>
      {!revealed
        ? <button type="button" className="wb-reveal no-print" onClick={() => setRevealed(true)}><Eye size={14} /> Reveal answer &amp; rationale</button>
        : <p className="wb-expected"><strong>{answerWithWhy(q.options[q.correctIndex], q.explanation)}</strong></p>}
    </article>
  )
}

function AnswerKeyPage({ chapter }) {
  const g = guidedWorkbookFor(chapter)
  const questions = validQuestions(chapter)
  return (
    <section className="wb-page wb-key-page">
      <header className="wb-lesson-head">
        <span className="wb-lesson-num">{chapter.number}</span>
        <div><p>{chapter.shortTitle}</p><h3>Answer key</h3></div>
      </header>
      <p className="wb-key-title">Concept checks</p>
      <ol className="wb-key-list">
        {g.concepts.map((item, i) => <li key={i}><strong>{item.prompt}</strong><br />{item.answer}</li>)}
      </ol>
      {g.patternChecks?.length > 0 && (
        <>
          <p className="wb-key-title">Pattern cases</p>
          <ol className="wb-key-list">
            {g.patternChecks.map((item, i) => <li key={i}><strong>{item.label}:</strong> {item.answer}</li>)}
          </ol>
        </>
      )}
      {g.matrix && (
        <>
          <p className="wb-key-title">{g.matrix.title || 'Classification table'} — completed</p>
          <table className="wb-matrix key">
            <thead><tr>{g.matrix.headers.map((h, i) => <th key={i}>{h}</th>)}</tr></thead>
            <tbody>{g.matrix.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}</tbody>
          </table>
        </>
      )}
      <p className="wb-key-title">Board questions</p>
      <ol className="wb-key-list">
        {questions.slice(0, 6).map((q, i) => (
          <li key={q.id}><strong>{String.fromCharCode(65 + q.correctIndex)}.</strong> {answerWithWhy(q.options[q.correctIndex], q.explanation)}</li>
        ))}
      </ol>
      <footer className="wb-foot"><span>Answer key · {chapter.shortTitle}</span><span>The FNP Workbook</span></footer>
    </section>
  )
}

function TrackerPage({ chapters }) {
  return (
    <section className="wb-page wb-tracker-page">
      <p className="wb-kicker">Progress tracker</p>
      <h2 className="wb-page-title">What I&apos;ve mastered — and what&apos;s next</h2>
      <p className="wb-lede">Date each lesson when you finish it. Bring the missed questions back in 3 days, then again in 2 weeks.</p>
      <table className="wb-tracker">
        <thead><tr><th>Chapter</th><th>Date done</th><th>Board Q score</th><th>Confidence (1–5)</th><th>Revisit date</th></tr></thead>
        <tbody>
          {chapters.map(c => (
            <tr key={c.id}><td>{c.number}. {c.shortTitle}</td><td /><td /><td /><td /></tr>
          ))}
        </tbody>
      </table>
      <p className="wb-mini-q" style={{ marginTop: 18 }}>My three weakest topics right now:</p>
      <div className="wb-tracker-lines"><i /><i /><i /></div>
      <p className="wb-cover-foot">© 2026 The FNP Workbook. All rights reserved. No part of this workbook may be reproduced or resold without permission. Educational use only; verify dosing and guidelines against current references.</p>
    </section>
  )
}
