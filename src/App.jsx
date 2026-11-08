import React, { useMemo, useState } from 'react'
import { useStore, streakOf, todayKey } from './lib/store'
import { useEffect } from 'react'
import { pdfUrlForChapter, manualIdForChapter } from './lib/pdfs'
import Reader, { Blocks } from './components/Reader.jsx'
import Quiz from './components/Quiz.jsx'
import Flashcards, { buildDecks } from './components/Flashcards.jsx'
import Planner from './components/Planner.jsx'
import Manuals from './components/Manuals.jsx'
import { House, Library, BookOpen, ClipboardCheck, Layers3, Zap, CalendarDays, Gem } from 'lucide-react'

const NAV = [
  ['dashboard', House, 'Dashboard'], ['library', Library, 'Study Guide'], ['manuals', BookOpen, 'Full Manuals'],
  ['quiz', ClipboardCheck, 'Practice & Exam'], ['flashcards', Layers3, 'Flashcards'], ['quickref', Zap, 'High-Yield'],
  ['planner', CalendarDays, 'Study Planner'], ['pricing', Gem, 'Go Pro'],
]

export default function App() {
  const [guide, setGuide] = useState(null)
  const [loadErr, setLoadErr] = useState('')
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/guide.json`).then(r => { if (!r.ok) throw new Error(r.status); return r.json() })
      .then(setGuide).catch(e => setLoadErr('Could not load study data (' + e.message + '). Check your connection and refresh.'))
  }, [])
  if (loadErr) return <div className="boot-screen"><div className="card boot-card"><p className="eyebrow">APEA 2026 FNP Study Hub</p><h2>Couldn't load study data</h2><p>{loadErr}</p><button className="btn" onClick={() => location.reload()}>Retry</button></div></div>
  if (!guide) return <div className="boot-screen"><div className="boot-card"><p className="eyebrow">APEA 2026</p><h1 className="serif">FNP Study Hub</h1><div className="boot-bar"><i/></div><p className="muted">Loading 21 chapters · 278 questions · 22 original manuals…</p></div></div>
  return <StudyApp guide={guide} />
}

function StudyApp({ guide }) {
  const [store, update] = useStore()
  const [view, setView] = useState(() => (location.hash.match(/^#\/([\w-]+)/)?.[1] || 'dashboard'))
  const [chapterId, setChapterId] = useState(() => location.hash.match(/^#\/reader\/([^/]+)/)?.[1] || null)
  const [manualId, setManualId] = useState(() => location.hash.match(/^#\/manuals\/(\d+)/)?.[1] || null)
  const [quizPreset, setQuizPreset] = useState(null)
  const [query, setQuery] = useState('')
  useEffect(() => {
    function sync() {
      const h = location.hash || '#/dashboard'
      const m = h.match(/^#\/([^/?]+)/)
      const v = m?.[1] || 'dashboard'
      if (v === 'reader') { setView('reader'); setChapterId(h.match(/^#\/reader\/([^/]+)/)?.[1] || null) }
      else if (v === 'manuals') { setView('manuals'); setManualId(h.match(/^#\/manuals\/(\d+)/)?.[1] || null) }
      else { setView(v); setManualId(null) }
    }
    window.addEventListener('hashchange', sync); return () => window.removeEventListener('hashchange', sync)
  }, [])
  const chapters = guide.chapters
  const chapter = chapters.find(c => c.id === chapterId)
  const totalQ = guide.meta.questions
  const answered = Object.keys(store.answers).length
  const correctCount = Object.values(store.answers).filter(a => a.correct).length
  const accuracy = answered ? Math.round(correctCount / answered * 100) : 0
  const doneCh = chapters.filter(c => store.completed[c.id]).length
  const decks = useMemo(() => buildDecks(guide, store), [store])
  const mastered = Object.values(decks).reduce((a, d) => a + d.cards.filter(c => (store.cardBox[c.id] || 0) >= 3).length, 0)
  const totalCards = decks.highyield.cards.length + decks.labs.cards.length
  const readiness = Math.round((doneCh / chapters.length) * 40 + (answered ? Math.min(answered / totalQ, 1) * 30 * (accuracy / 100 + 0.3) / 1.3 : 0) + Math.min(mastered / Math.max(1, totalCards), 1) * 30)
  const streak = streakOf(store.studyDates)
  const lastChapter = chapters.find(c => c.id === store.lastChapter) || chapters.find(c => !store.completed[c.id])

  const searchResults = useMemo(() => {
    if (query.trim().length < 3) return []
    const q = query.toLowerCase(); const out = []
    chapters.forEach(c => c.sections.forEach(s => s.blocks.forEach(b => {
      const texts = b.type === 'table' ? [b.headers.join(' '), ...b.rows.map(r => r.join(' '))] : b.type === 'list' ? b.items : [b.text]
      texts.forEach(t => { if (t && t.toLowerCase().includes(q) && out.length < 40) out.push({ chapter: c, section: s.title, text: t }) })
    })))
    return out
  }, [query])

  function openQuiz(chId) { setQuizPreset(chId ? { mode: 'practice', chapterId: chId } : null); go('quiz') }
  function openChapter(id) { setChapterId(id); setView('reader'); location.hash = `#/reader/${id}`; window.scrollTo(0, 0) }
  function openManual(id) { setManualId(id); go('manuals'); location.hash = id ? `#/manuals/${id}` : '#/manuals' }
  function go(v) {
    setView(v); if (v !== 'quiz') setQuizPreset(null); if (v !== 'manuals') setManualId(null)
    if (v !== 'reader') location.hash = `#/${v}`
    window.scrollTo(0, 0)
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="logo">APEA 2026<br /><span>FNP Study Hub</span></div>
        <p className="tagline">The all-in-one board-prep system: full guide, questions, flashcards, exam simulator & planner.</p>
        {NAV.map(([k, Icon, label]) => <button key={k} className={`navbtn ${view === k ? 'active' : ''}`} onClick={() => go(k)}><Icon size={18} strokeWidth={2} />{label}</button>)}
        <div className="sidefoot">
          <p className="sidefoot-label">Board readiness</p>
          <strong>{readiness}%</strong>
          <div className="bar side-bar"><i style={{ width: `${readiness}%` }} /></div>
          <p>{doneCh}/{chapters.length} chapters · {answered}/{totalQ} Qs</p>
          <p>{streak}-day streak</p>
        </div>
      </aside>

      <main>
        {['dashboard', 'library', 'quickref'].includes(view) && (
          <div className="top-search">
            <input id="guide-search" name="guide-search" type="text" aria-label="Search the complete study guide" placeholder="Search the study guide — torsades, CURB-65, metformin…" value={query} onChange={e => setQuery(e.target.value)} />
            {query && <button className="btn ghost" onClick={() => setQuery('')}>Clear</button>}
          </div>
        )}
        {query.trim().length >= 3 ? (
          <div><h2>Search results ({searchResults.length})</h2>
            {searchResults.map((r, i) => <div className="card" key={i} style={{ margin: '10px 0', cursor: 'pointer' }} onClick={() => { openChapter(r.chapter.id); setQuery('') }}>
              <p className="label">{r.chapter.number}. {r.chapter.shortTitle} · {r.section}</p><p className="small">{r.text.slice(0, 320)}…</p></div>)}
            {!searchResults.length && <div className="card">No matches. Try a shorter term.</div>}
          </div>
        ) : (<>
          {view === 'dashboard' && (
            <div>
              <div className="hero">
                <p className="pill gold">APEA 2026 · FNP / AGPCNP · AANP + ANCC</p>
                <h1>Pass your FNP boards.<br />One hub, everything you need.</h1>
                <p>All 21 study-guide chapters plus every page of the 22 original APEA 2026 manuals — searchable and turned into {totalQ} practice questions, flashcards, a timed exam simulator and a day-by-day study plan. No more juggling 1.2 GB of PDFs.</p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
                  <button className="btn gold" onClick={() => { if (lastChapter) openChapter(lastChapter.id) }}>{store.lastChapter ? 'Continue studying →' : 'Start Chapter 1 →'}</button>
                  <button className="btn" onClick={() => openQuiz()}>Take a practice quiz</button>
                  <button className="btn ghost" onClick={() => go('manuals')}>Browse all 22 full manuals</button>
                </div>
              </div>
              <div className="grid cols4" style={{ marginTop: 16 }}>
                <div className="card"><p className="label">Board readiness</p><p className="stat">{readiness}%</p><div className="bar"><i style={{ width: `${readiness}%` }} /></div><p className="small muted">Chapters 40% · questions 30% · flashcards 30%</p></div>
                <div className="card"><p className="label">Chapters complete</p><p className="stat">{doneCh}/{chapters.length}</p><div className="bar"><i style={{ width: `${doneCh / chapters.length * 100}%` }} /></div><p className="small muted">{chapters.reduce((a, c) => a + c.wordCount, 0).toLocaleString()} words of guide</p></div>
                <div className="card"><p className="label">Question accuracy</p><p className="stat">{answered ? accuracy + '%' : '—'}</p><p className="small muted">{correctCount}/{answered} correct · {totalQ - answered} untouched<br />75%+ is board-ready pace</p></div>
                <div className="card"><p className="label">Study streak</p><p className="stat">{streak} day{streak === 1 ? '' : 's'}</p><p className="small muted">{mastered} flashcards mastered · {store.studyDates.length} total study days</p></div>
              </div>
              <TodayReview store={store} decks={decks} guide={guide} go={go} openQuiz={openQuiz} />
              <WeakAreas guide={guide} store={store} onQuiz={(id) => openQuiz(id)} onRead={(id) => openChapter(id)} />
              <Blueprint guide={guide} />
              <div className="grid cols2" style={{ marginTop: 16 }}>
                <div className="card"><h3 style={{ marginTop: 0 }}>Your fastest path to ready</h3>
                  <ol style={{ lineHeight: 2, color: 'var(--ink2)', paddingLeft: 20 }}>
                    <li>Read a chapter, then immediately do its practice questions.</li>
                    <li>Missed questions auto-collect into a personal deck — drill them daily.</li>
                    <li>Run the 50-question timed simulator weekly at AANP pace (72s/question).</li>
                    <li>Finish with the High-Yield Quick Reference until it's memorized.</li>
                  </ol>
                  <button className="btn" onClick={() => go('planner')}>Build my study plan →</button>
                </div>
                <div className="card"><h3 style={{ marginTop: 0 }}>What's inside Pro</h3>
                  <ul style={{ lineHeight: 2, color: 'var(--ink2)', paddingLeft: 20 }}>
                    <li><strong>{chapters.length} chapters</strong> — the complete APEA 2026 manual, fully searchable</li>
                    <li><strong>{totalQ} practice questions</strong> with Answer-Key rationales</li>
                    <li><strong>{totalCards}+ flashcards</strong> (High-Yield + Labs) plus question cards</li>
                    <li>Timed exam simulator, missed-question deck, original PDFs, planner</li>
                  </ul>
                  <button className="btn gold" onClick={() => go('pricing')}>See Pro pricing →</button>
                </div>
              </div>
              <h2 style={{ marginTop: 28 }}>Chapters</h2>
              <div className="card">{chapters.slice(0, 6).map(c => <ChapterRow key={c.id} c={c} store={store} onOpen={() => openChapter(c.id)} />)}
                <button className="btn ghost" style={{ marginTop: 12 }} onClick={() => go('library')}>View all {chapters.length} chapters →</button></div>
            </div>
          )}

          {view === 'library' && (
            <div><h1>Study Guide — all {chapters.length} chapters</h1>
              <p className="muted">In manual order, with the original course PDF for every chapter. Mark chapters complete to build your readiness score.</p>
              <div className="card">{chapters.map(c => <ChapterRow key={c.id} c={c} store={store} onOpen={() => openChapter(c.id)} />)}</div>
            </div>
          )}


          {view === 'reader' && chapter && (
            <Reader chapter={chapter} store={store} update={update} onBack={() => go('library')} onQuiz={openQuiz}
              onOpenManual={() => openManual(manualIdForChapter(chapter))}
              onNext={() => { const n = chapters[chapters.indexOf(chapter) + 1]; if (n) openChapter(n.id) }} />
          )}

          {view === 'manuals' && <Manuals initialId={manualId} />}

          {view === 'quiz' && <Quiz key={quizPreset ? quizPreset.chapterId + quizPreset.mode : 'setup'} guide={guide} store={store} update={update} preset={quizPreset} />}
          {view === 'flashcards' && <Flashcards guide={guide} store={store} update={update} />}

          {view === 'quickref' && (
            <div style={{ maxWidth: 860, margin: '0 auto' }}><h1>⚡ High-Yield Quick Reference</h1>
              <p className="muted">The numbers and rules the exam loves — from the guide's Quick Reference plus the labs to commit to memory. Search it, then drill it in Flashcards.</p>
              {(guide.quickRef?.sections || []).map(s => <div key={s.id}><h3>{s.title}</h3><Blocks blocks={s.blocks} /></div>)}
              {chapters[0].sections.filter(s => /labs/i.test(s.title)).map(s => <div key={s.id}><h3>{s.title}</h3><Blocks blocks={s.blocks} /></div>)}
              <button className="btn" onClick={() => go('flashcards')}>Drill these as flashcards →</button>
            </div>
          )}

          {view === 'planner' && <Planner guide={guide} store={store} update={update} />}

          {view === 'pricing' && <Pricing store={store} update={update} totalQ={totalQ} totalCards={totalCards} chapters={chapters.length} />}
        </>)}
      </main>

      <nav className="bottomnav">
        {NAV.slice(0, 5).map(([k, Icon, label]) => <button key={k} className={view === k ? 'active' : ''} onClick={() => go(k)}><Icon size={19} /><br />{label.split(' ')[0]}</button>)}
      </nav>
    </div>
  )
}

function TodayReview({ store, decks, guide, go, openQuiz }) {
  const due = [...decks.highyield.cards, ...decks.labs.cards].filter(c => (store.cardBox[c.id] || 0) < 3).length
  const missed = Object.values(store.answers).filter(a => !a.correct).length
  const today = (store.daily || {})[todayKey()] || {}
  return (
    <div className="card" style={{ marginTop: 16, border: '2px solid var(--brand)' }}>
      <h3 style={{ marginTop: 0 }}>Today's Review — your smart session</h3>
      <p className="muted" style={{ lineHeight: 1.6 }}>Today: <strong>{today.answered || 0}</strong> questions answered · <strong>{today.cards || 0}</strong> flashcards rated · <strong>{missed}</strong> missed questions waiting · <strong>{due}</strong> high-yield/lab cards not yet mastered. Ten focused minutes here beats an hour of re-reading.</p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button className="btn" onClick={() => go('flashcards')}>Review flashcards ({due} due)</button>
        <button className="btn gold" disabled={!missed} onClick={() => openQuiz()}>Drill missed questions ({missed})</button>
        <button className="btn ghost" onClick={() => go('quickref')}>⚡ High-yield cram sheet</button>
      </div>
      {!store.examDate && <p className="small" style={{ marginTop: 10 }}>No exam date set — <a href="#" onClick={e => { e.preventDefault(); go('planner') }}>set one in the Study Planner</a> to get your day-by-day countdown plan.</p>}
      {store.examDate && <p className="small" style={{ marginTop: 10 }}>Exam: <strong>{new Date(store.examDate + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</strong> — {Math.max(0, Math.round((new Date(store.examDate) - Date.now()) / 86400000))} days to go.</p>}
    </div>
  )
}

function WeakAreas({ guide, store, onQuiz, onRead }) {
  const qChapter = useMemo(() => { const m = {}; guide.chapters.forEach(c => c.questions.forEach(q => { m[q.id] = c })); return m }, [guide])
  const rows = useMemo(() => {
    const by = {}
    Object.entries(store.answers).forEach(([qid, a]) => { const c = qChapter[qid]; if (!c) return; by[c.id] = by[c.id] || { chapter: c, t: 0, ok: 0 }; by[c.id].t++; if (a.correct) by[c.id].ok++ })
    return Object.values(by).map(r => ({ ...r, pct: Math.round(r.ok / r.t * 100) })).sort((a, b) => a.pct - b.pct)
  }, [store.answers, qChapter])
  if (!rows.length) return (
    <div className="card" style={{ marginTop: 16 }}><h3 style={{ marginTop: 0 }}>Weak-area radar</h3>
      <p className="muted">Answer practice questions and this fills in with your accuracy by chapter — so you always know exactly what to study next instead of guessing.</p></div>
  )
  return (
    <div className="card" style={{ marginTop: 16 }}><h3 style={{ marginTop: 0 }}>Weak-area radar — study what you're actually missing</h3>
      {rows.map(r => (
        <div key={r.chapter.id} style={{ display: 'flex', gap: 10, alignItems: 'center', margin: '10px 0', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 220px' }}><strong>{r.chapter.shortTitle}</strong><span className="muted small"> · {r.ok}/{r.t} correct</span>
            <div className="bar"><i style={{ width: r.pct + '%', background: r.pct >= 75 ? 'var(--green)' : r.pct >= 55 ? 'var(--gold)' : 'var(--red)' }} /></div></div>
          <span className="pill" style={r.pct < 55 ? { background: '#fdecec', color: 'var(--red)' } : {}}>{r.pct}%</span>
          {r.pct < 75 && <><button className="btn ghost" onClick={() => onRead(r.chapter.id)}>Re-read</button><button className="btn" onClick={() => onQuiz(r.chapter.id)}>Quiz it</button></>}
        </div>
      ))}
      <DataTools store={store} />
    </div>
  )
}

function DataTools({ store }) {
  function exportData() {
    const blob = new Blob([JSON.stringify(store, null, 2)], { type: 'application/json' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'apea-study-progress.json'; a.click(); URL.revokeObjectURL(a.href)
  }
  function importData(e) {
    const f = e.target.files[0]; if (!f) return
    f.text().then(txt => { try { const data = JSON.parse(txt); localStorage.setItem('apea-hub-v2', JSON.stringify(data)); location.reload() } catch { alert('That file is not a valid progress backup.') } })
  }
  return (
    <div style={{ borderTop: '1px solid var(--line)', marginTop: 14, paddingTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
      <span className="label">Your data</span>
      <button className="btn ghost" onClick={exportData}>Export progress</button>
      <label className="btn ghost" style={{ cursor: 'pointer' }}>Import progress<input type="file" accept="application/json" hidden onChange={importData} /></label>
      <button className="btn ghost" onClick={() => { if (confirm('Reset ALL progress, bookmarks and quiz history on this device?')) { localStorage.removeItem('apea-hub-v2'); location.reload() } }}>Reset everything</button>
      <span className="small muted">Progress lives on this device — export before switching phones/computers.</span>
    </div>
  )
}

function Blueprint({ guide }) {
  const ch1 = guide.chapters[0]
  const tables = []
  ch1?.sections.forEach(s => s.blocks.forEach(b => { if (b.type === 'table' && tables.length < 3) tables.push({ section: s.title, ...b }) }))
  if (!tables.length) return null
  return (
    <div className="card" style={{ marginTop: 16 }}><h3 style={{ marginTop: 0 }}>Know your exam — AANP vs ANCC blueprint</h3>
      <p className="muted small">Straight from Chapter 1 of your manual. Pick one exam, study to its blueprint.</p>
      {tables.map((tb, i) => <div key={i}><p className="label" style={{ marginTop: 12 }}>{tb.section}</p>
        <div className="tablewrap"><table><thead><tr>{tb.headers.map((h, j) => <th key={j}>{h}</th>)}</tr></thead><tbody>{tb.rows.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{c}</td>)}</tr>)}</tbody></table></div></div>)}
    </div>
  )
}

function ChapterRow({ c, store, onOpen }) {
  const done = !!store.completed[c.id]
  return (
    <div className="chapter">
      <div className={`num ${done ? 'done' : ''}`}>{done ? '✓' : c.number}</div>
      <div style={{ flex: 1, cursor: 'pointer' }} onClick={onOpen}>
        <strong>{c.shortTitle}</strong>
        <p className="small muted" style={{ margin: 2 }}>{c.sections.length} sections · ~{Math.max(1, Math.round(c.wordCount / 200))} min · {c.questions.length} questions {store.bookmarks.includes(c.id) ? '· ★ bookmarked' : ''}</p>
      </div>
      <a className="pill" href={pdfUrlForChapter(c)} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}>PDF</a>
      <button className="btn ghost" onClick={onOpen}>Study →</button>
    </div>
  )
}

function Pricing({ store, update, totalQ, totalCards, chapters }) {
  const [email, setEmail] = useState(''); const [joined, setJoined] = useState(false)
  const features = ['Complete 21-chapter APEA 2026 study guide (searchable)', `${totalQ} practice questions with rationales`, 'Timed AANP-pace exam simulator', `${totalCards}+ high-yield & lab flashcards`, 'Missed-question smart deck', 'All 22 original manuals (full searchable text + PDFs)', 'Personal study planner + readiness score', 'New 2026 guideline updates included']
  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }}>
      <h1 style={{ textAlign: 'center' }}>Study like you mean it.</h1>
      <p className="muted" style={{ textAlign: 'center' }}>One hub instead of 22 PDFs, random Quizlet decks and guesswork.</p>
      <div className="grid cols2" style={{ marginTop: 20 }}>
        <div className="card"><p className="label">Free</p><p className="price">$0</p>
          <ul style={{ lineHeight: 2, color: 'var(--ink2)' }}>{features.slice(0, 3).map(f => <li key={f}>{f}</li>)}<li className="muted">Dashboard preview & Chapter 1</li></ul>
          <button className="btn ghost" onClick={() => window.scrollTo(0, 0)}>You're using it now</button></div>
        <div className="card" style={{ border: '2px solid var(--gold)' }}><p className="pill gold">Most popular · Pro</p><p className="price">$39<span style={{ fontSize: 16 }}>/exam season</span></p>
          <ul style={{ lineHeight: 2, color: 'var(--ink2)' }}>{features.map(f => <li key={f}>{f}</li>)}</ul>
          {joined ? <p style={{ background: '#e6f5ec', padding: 12, borderRadius: 10 }}><strong>You're on the list.</strong> We'll email your Pro invite the moment checkout opens.</p>
            : <form onSubmit={e => { e.preventDefault(); if (!email.includes('@')) return; update(s => ({ ...s, waitlist: [...s.waitlist, { email, at: todayKey() }] })); setJoined(true) }}>
              <input type="email" required placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} />
              <button className="btn gold" style={{ width: '100%', marginTop: 10 }}>Join the Pro waitlist →</button>
              <p className="small muted">Checkout opens soon. Waitlist members lock the $39 launch price (regular $59).</p></form>}
        </div>
      </div>
      <div className="card" style={{ marginTop: 16 }}><h3 style={{ marginTop: 0 }}>Why students pay for this</h3>
        <p style={{ lineHeight: 1.7, color: 'var(--ink2)' }}>The APEA review manual is excellent — and unusable as 22 giant PDFs the month before your exam. This hub turns that exact trusted content into a system: read a chapter, get quizzed on it instantly, watch your misses become flashcards, and know — with a real readiness score — whether you're going to pass before you sit down. That's the difference between hoping and knowing.</p></div>
    </div>
  )
}
