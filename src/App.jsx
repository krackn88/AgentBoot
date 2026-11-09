import React, { lazy, Suspense, useMemo, useState, useEffect } from 'react'
import { useStore, streakOf, todayKey } from './lib/store'
import { pdfUrlForChapter, manualIdForChapter } from './lib/pdfs'
import Reader, { Blocks } from './components/Reader.jsx'
import Quiz from './components/Quiz.jsx'
import Flashcards, { buildDecks } from './components/Flashcards.jsx'
import Planner from './components/Planner.jsx'
import Workbook from './components/Workbook.jsx'
import { Sidebar, PageHeader, MobileNav } from './components/AppShell.jsx'
import PlatformStats from './components/PlatformStats.jsx'
import StudyPath from './components/StudyPath.jsx'
import OnboardingCard from './components/OnboardingCard.jsx'
import Milestones from './components/Milestones.jsx'
import { ReadinessReportCard, ReadinessCertificate } from './components/ReadinessTools.jsx'
import ContextualHelp from './components/ContextualHelp.jsx'
import ViewSkeleton from './components/ViewSkeleton.jsx'
import { usePageTitle } from './lib/usePageTitle'
import { BETA_OPEN } from './lib/config'
import { flattenQuestions, gradable } from './lib/questions'
import { buildTwelveWeekPath } from './lib/studyPath'
import { countCompletedPathWeeks } from './lib/milestones'
import { PLANS, COMPARE_ROWS } from './lib/plans'
import { loadGuide, loadPlatformBundle, prefetchChapterModule } from './lib/platform'

const Manuals = lazy(() => import('./components/Manuals.jsx'))
const Tests = lazy(() => import('./components/Tests.jsx'))

export default function App() {
  const [guide, setGuide] = useState(null)
  const [loadErr, setLoadErr] = useState('')
  useEffect(() => {
    loadGuide()
      .then(setGuide)
      .catch(e => setLoadErr('Could not load study data (' + e.message + '). Check your connection and refresh.'))
  }, [])
  if (loadErr) return <div className="boot-screen"><div className="card boot-card"><p className="eyebrow">APEA 2026 FNP Study Hub</p><h2>Couldn't load study data</h2><p>{loadErr}</p><button className="btn" onClick={() => location.reload()}>Retry</button></div></div>
  if (!guide) return <div className="boot-screen"><div className="boot-card"><p className="eyebrow">APEA 2026</p><h1 className="serif">FNP Board Prep</h1><div className="boot-bar"><i/></div><p className="muted">Loading study guide, manuals, workbooks, and question banks…</p></div></div>
  return <StudyApp guide={guide} />
}

function StudyApp({ guide }) {
  const [store, update] = useStore()
  const [view, setView] = useState(() => (location.hash.match(/^#\/([\w-]+)/)?.[1] || 'dashboard'))
  const [chapterId, setChapterId] = useState(() => location.hash.match(/^#\/reader\/([^/]+)/)?.[1] || null)
  const [manualId, setManualId] = useState(() => location.hash.match(/^#\/manuals\/(\d+)/)?.[1] || null)
  const [quizPreset, setQuizPreset] = useState(null)
  const [query, setQuery] = useState('')
  const [searchCorpus, setSearchCorpus] = useState([])
  const [contentMeta, setContentMeta] = useState(null)
  const [pearlCards, setPearlCards] = useState([])
  const [manualBank, setManualBank] = useState(null)
  useEffect(() => {
    function sync() {
      const h = location.hash || '#/dashboard'
      const m = h.match(/^#\/([^/?]+)/)
      const v = m?.[1] || 'dashboard'
      if (v === 'reader') { setView('reader'); setChapterId(h.match(/^#\/reader\/([^/]+)/)?.[1] || null) }
      else if (v === 'manuals') { setView('manuals'); setManualId(h.match(/^#\/manuals\/(\d+)/)?.[1] || null) }
      else if (v === 'pricing') { setView('about'); history.replaceState(null, '', '#/about') }
      else { setView(v); setManualId(null) }
    }
    window.addEventListener('hashchange', sync); return () => window.removeEventListener('hashchange', sync)
  }, [])
  useEffect(() => {
    loadPlatformBundle().then(({ searchCorpus, pearlCards, contentMeta, manualBank }) => {
      setSearchCorpus(searchCorpus)
      setPearlCards(pearlCards)
      setContentMeta(contentMeta)
      setManualBank(manualBank)
    }).catch(() => {})
  }, [])
  const chapters = guide.chapters
  const questionPool = useMemo(() => flattenQuestions(guide, manualBank), [guide, manualBank])
  const gradedQ = useMemo(() => gradable(questionPool).length, [questionPool])
  const chapter = chapters.find(c => c.id === chapterId)
  const guideQCount = guide.meta.questions
  const manualQCount = manualBank?.meta?.graded ?? 0
  const totalQ = gradedQ || guideQCount + manualQCount
  const answered = Object.keys(store.answers).length
  const correctCount = Object.values(store.answers).filter(a => a.correct).length
  const accuracy = answered ? Math.round(correctCount / answered * 100) : 0
  const doneCh = chapters.filter(c => store.completed[c.id]).length
  const decks = useMemo(() => buildDecks(guide, store, pearlCards, questionPool), [guide, store, pearlCards, questionPool])
  const mastered = Object.values(decks).reduce((a, d) => a + d.cards.filter(c => (store.cardBox[c.id] || 0) >= 3).length, 0)
  const totalCards = decks.highyield.cards.length + decks.labs.cards.length
  const readiness = Math.round((doneCh / chapters.length) * 40 + (answered ? Math.min(answered / totalQ, 1) * 30 * (accuracy / 100 + 0.3) / 1.3 : 0) + Math.min(mastered / Math.max(1, totalCards), 1) * 30)
  const streak = streakOf(store.studyDates)
  const lastChapter = chapters.find(c => c.id === store.lastChapter) || chapters.find(c => !store.completed[c.id])
  const pathWeeks = useMemo(() => buildTwelveWeekPath(guide), [guide])
  const weeksComplete = countCompletedPathWeeks(pathWeeks, store.studyPathDone)
  const milestoneStats = { doneCh, totalCh: chapters.length, answered, accuracy, mastered, streak, readiness }

  const searchResults = useMemo(() => {
    if (query.trim().length < 3) return []
    const q = query.toLowerCase(); const out = []
    chapters.forEach(c => c.sections.forEach(s => s.blocks.forEach(b => {
      const texts = b.type === 'table' ? [b.headers.join(' '), ...b.rows.map(r => r.join(' '))] : (b.type === 'list' || b.type === 'manual-list') ? b.items : [b.text]
      texts.forEach(t => { if (t && t.toLowerCase().includes(q) && out.length < 50) out.push({ chapter: c, section: s.title, text: t, source: 'guide' }) })
    })))
    for (const hit of searchCorpus) {
      if (out.length >= 50) break
      if (hit.text?.toLowerCase().includes(q)) {
        const c = chapters.find(x => x.id === hit.chapterId)
        if (c) out.push({ chapter: c, section: hit.section, text: hit.text, source: hit.section === 'Clinical pearl' ? 'pearl' : 'manual' })
      }
    }
    return out
  }, [query, searchCorpus, chapters])

  function openQuiz(chId) { setQuizPreset(chId ? { mode: 'practice', chapterId: chId } : null); go('quiz') }
  function openChapter(id) { setChapterId(id); setView('reader'); location.hash = `#/reader/${id}`; window.scrollTo(0, 0) }
  function openManual(id) { setManualId(id); go('manuals'); location.hash = id ? `#/manuals/${id}` : '#/manuals' }
  function go(v) {
    setView(v); if (v !== 'quiz') setQuizPreset(null); if (v !== 'manuals') setManualId(null)
    if (v !== 'reader') location.hash = `#/${v}`
    window.scrollTo(0, 0)
  }

  const titles = {
    dashboard: 'Dashboard', library: 'Study guide', manuals: 'Full manuals', reader: chapter?.shortTitle,
    quiz: 'Question bank', tests: 'Mock exams', workbooks: 'Workbooks', flashcards: 'Flashcards',
    quickref: 'High-yield', planner: 'Study planner', about: 'About',
  }
  usePageTitle(titles[view] || null)

  return (
    <div className="layout">
      <Sidebar view={view} go={go} readiness={readiness} doneCh={doneCh} totalCh={chapters.length} answered={answered} totalQ={totalQ} guideQ={guideQCount} manualQ={manualQCount} streak={streak} />

      <main className="main-shell">
        {['dashboard', 'tests', 'reader'].includes(view) && <ContextualHelp view={view === 'reader' ? 'reader' : view} />}
        {BETA_OPEN && view === 'dashboard' && (
          <div className="beta-banner no-print">
            <strong>Open beta.</strong> Every chapter, workbook, mock exam, flashcard deck, and manual is unlocked while we finish polishing the platform. Your progress still saves on this device.
          </div>
        )}
        {['dashboard', 'library', 'quickref'].includes(view) && (
          <div className="top-search">
            <input id="guide-search" name="guide-search" type="text" aria-label="Search the complete study guide" placeholder="Search the study guide — torsades, CURB-65, metformin…" value={query} onChange={e => setQuery(e.target.value)} />
            {query && <button className="btn ghost" onClick={() => setQuery('')}>Clear</button>}
          </div>
        )}
        {query.trim().length >= 3 ? (
          <div><h2>Search results ({searchResults.length})</h2>
            {searchResults.map((r, i) => <div className="card search-hit" key={i} style={{ margin: '10px 0', cursor: 'pointer' }} onClick={() => { openChapter(r.chapter.id); setQuery('') }}>
              <p className="label">{r.chapter.number}. {r.chapter.shortTitle} · {r.section} {r.source !== 'guide' && <span className="pill">{r.source === 'pearl' ? 'Pearl' : 'Manual'}</span>}</p><p className="small">{r.text.slice(0, 320)}…</p></div>)}
            {!searchResults.length && <div className="card">No matches. Try a shorter term.</div>}
          </div>
        ) : (<>
          {view === 'dashboard' && (
            <div>
              <OnboardingCard onGo={go} />
              <div className="hero">
                <p className="pill gold">One path to exam day</p>
                <h1>See how ready you are — not just how much you read.</h1>
                <p>Searchable chapters, timed mocks, weak-area tracking, and a printable readiness report — built from the official APEA 2026 manuals on this server.</p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
                  <button className="btn gold" onClick={() => { if (lastChapter) openChapter(lastChapter.id) }}>{store.lastChapter ? 'Continue studying →' : 'Start Chapter 1 →'}</button>
                  <button className="btn" onClick={() => openQuiz()}>Take a practice quiz</button>
                  <button className="btn ghost" onClick={() => go('manuals')}>Browse all 22 full manuals</button>
                </div>
              </div>
              <ReadinessCertificate readiness={readiness} doneCh={doneCh} totalCh={chapters.length} accuracy={accuracy} streak={streak} examDate={store.examDate} />
              <PlatformStats guide={guide} contentMeta={contentMeta} manualBank={manualBank} questionTotal={totalQ} />
              <ReadinessReportCard guide={guide} store={store} readiness={readiness} doneCh={doneCh} totalCh={chapters.length} answered={answered} totalQ={totalQ} accuracy={accuracy} mastered={mastered} streak={streak} />
              <Milestones store={store} stats={milestoneStats} weeksComplete={weeksComplete} />
              <div className="grid cols4" style={{ marginTop: 16 }}>
                <div className="card"><p className="label">Board readiness</p><p className="stat">{readiness}%</p><div className="bar"><i style={{ width: `${readiness}%` }} /></div><p className="small muted">Chapters 40% · questions 30% · flashcards 30%</p></div>
                <div className="card"><p className="label">Chapters complete</p><p className="stat">{doneCh}/{chapters.length}</p><div className="bar"><i style={{ width: `${doneCh / chapters.length * 100}%` }} /></div><p className="small muted">{chapters.reduce((a, c) => a + c.wordCount, 0).toLocaleString()} words of guide</p></div>
                <div className="card"><p className="label">Question accuracy</p><p className="stat">{answered ? accuracy + '%' : '—'}</p><p className="small muted">{correctCount}/{answered} correct · {totalQ - answered} untouched<br />75%+ is board-ready pace</p></div>
                <div className="card"><p className="label">Study streak</p><p className="stat">{streak} day{streak === 1 ? '' : 's'}</p><p className="small muted">{mastered} flashcards mastered · {store.studyDates.length} total study days</p></div>
              </div>
              <StudyPath guide={guide} store={store} update={update} onOpenChapter={openChapter} onGo={go} />
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
                <div className="card platform-card">
                  <h3 style={{ marginTop: 0 }}>Everything in one place</h3>
                  <ul className="feature-list">
                    <li><strong>{chapters.length} chapters</strong> — searchable study guide with original PDFs</li>
                    <li><strong>22 manuals</strong> — full text + source PDFs from the APEA course</li>
                    <li><strong>1,720+ workbook drills</strong> — active recall from clinical tables</li>
                    <li><strong>{totalQ} questions</strong> — graded with Answer Key rationales</li>
                    <li><strong>Mock exams</strong> — AANP, ANCC, and chapter tests</li>
                    {contentMeta && <li><strong>{contentMeta.pearls_total} clinical pearls</strong> + manual depth on every chapter</li>}
                    {manualBank?.meta?.graded > 0 && <li><strong>{manualBank.meta.graded}</strong> extra MCQs from course-manual slides (separate mock banks)</li>}
                  </ul>
                </div>
              </div>
              <h2 style={{ marginTop: 28 }}>Chapters</h2>
              <div className="card">{chapters.slice(0, 6).map(c => <ChapterRow key={c.id} c={c} store={store} contentMeta={contentMeta} onOpen={() => openChapter(c.id)} />)}
                <button className="btn ghost" style={{ marginTop: 12 }} onClick={() => go('library')}>View all {chapters.length} chapters →</button></div>
            </div>
          )}

          {view === 'library' && (
            <div>
              <PageHeader eyebrow="Study guide" title={`All ${chapters.length} chapters`} subtitle="Condensed guide plus Course manual depth and Clinical pearls tabs in each chapter — sourced from the full APEA manuals on your server." />
              <div className="card">{chapters.map(c => <ChapterRow key={c.id} c={c} store={store} contentMeta={contentMeta} onOpen={() => openChapter(c.id)} />)}</div>
            </div>
          )}


          {view === 'reader' && chapter && (
            <Reader chapter={chapter} store={store} update={update} onBack={() => go('library')} onQuiz={openQuiz}
              onOpenManual={() => openManual(manualIdForChapter(chapter))}
              onNext={() => { const n = chapters[chapters.indexOf(chapter) + 1]; if (n) openChapter(n.id) }} />
          )}

          {view === 'manuals' && (
            <Suspense fallback={<ViewSkeleton label="Loading manuals" />}>
              <Manuals initialId={manualId} />
            </Suspense>
          )}

          {view === 'quiz' && <Quiz key={quizPreset ? (quizPreset.testId || quizPreset.chapterId + quizPreset.mode) : 'setup'} guide={guide} store={store} update={update} preset={quizPreset} questionPool={questionPool} />}
          {view === 'flashcards' && <Flashcards guide={guide} store={store} update={update} pearlCards={pearlCards} questionPool={questionPool} />}
          {view === 'tests' && (
            <Suspense fallback={<ViewSkeleton label="Loading mock exams" />}>
              <Tests guide={guide} store={store} questionPool={questionPool} onStart={(p) => { setQuizPreset(p); setView('quiz'); location.hash = '#/quiz'; window.scrollTo(0, 0) }} />
            </Suspense>
          )}
          {view === 'workbooks' && <Workbook guide={guide} store={store} update={update} pearlCards={pearlCards} />}

          {view === 'quickref' && (
            <div style={{ maxWidth: 860, margin: '0 auto' }}>
              <PageHeader eyebrow="High yield" title="Quick reference + clinical pearls" subtitle="Condensed rules from the study guide, labs to memorize, and the highest-signal lines pulled from all 22 course manuals." />
              {(guide.quickRef?.sections || []).map(s => <div key={s.id} className="card" style={{ marginBottom: 16 }}><h3>{s.title}</h3><Blocks blocks={s.blocks} /></div>)}
              {chapters[0].sections.filter(s => /labs/i.test(s.title)).map(s => <div key={s.id} className="card" style={{ marginBottom: 16 }}><h3>{s.title}</h3><Blocks blocks={s.blocks} /></div>)}
              {pearlCards.length > 0 && (
                <div className="card">
                  <h3>Clinical pearls sampler</h3>
                  <p className="muted small">A taste of the {pearlCards.length} pearl cards — open any chapter's Clinical pearls tab or drill the full deck in Flashcards.</p>
                  <div className="pearl-grid">{pearlCards.slice(0, 12).map((p, i) => (
                    <div key={p.id} className="pearl-card"><span className="pearl-num">{i + 1}</span><p>{p.front}</p></div>
                  ))}</div>
                  <button className="btn" style={{ marginTop: 14 }} onClick={() => go('flashcards')}>Drill all pearls in flashcards →</button>
                </div>
              )}
              <button className="btn ghost" onClick={() => go('flashcards')}>High-yield & lab flashcard decks →</button>
            </div>
          )}

          {view === 'planner' && <Planner guide={guide} store={store} update={update} />}

          {view === 'about' && <AboutAccess totalQ={totalQ} totalCards={totalCards} chapters={chapters.length} store={store} update={update} guide={guide} contentMeta={contentMeta} manualBank={manualBank} readiness={readiness} />}
        </>)}
      </main>

<MobileNav view={view} go={go} />
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

function ChapterRow({ c, store, onOpen, contentMeta }) {
  const done = !!store.completed[c.id]
  const depth = contentMeta?.chapters?.find(x => x.id === c.id)
  const graded = c.questions.filter(q => q.correctIndex != null && q.options?.length >= 2).length
  return (
    <div className="chapter chapter-row-pro" onMouseEnter={() => prefetchChapterModule(c.id)}>
      <div className={`num ${done ? 'done' : ''}`}>{done ? '✓' : c.number}</div>
      <div style={{ flex: 1, cursor: 'pointer' }} onClick={onOpen}>
        <strong>{c.shortTitle}</strong>
        <p className="small muted" style={{ margin: 2 }}>{c.sections.length} sections · ~{Math.max(1, Math.round(c.wordCount / 200))} min · {graded} Q{depth ? ` · ${depth.pearls} pearls · ${(depth.words / 1000).toFixed(1)}k manual depth` : ''} {store.bookmarks.includes(c.id) ? '· ★ saved' : ''}</p>
      </div>
      <a className="pill" href={pdfUrlForChapter(c)} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}>PDF</a>
      <button className="btn ghost" onClick={onOpen}>Study →</button>
    </div>
  )
}

function AboutAccess({ totalQ, totalCards, chapters, store, update, guide, contentMeta, manualBank, readiness }) {
  const [email, setEmail] = useState('')
  const [note, setNote] = useState('')
  const [joined, setJoined] = useState(false)
  const pearls = contentMeta?.pearls_total ?? 0
  const pro = PLANS.pro
  const free = PLANS.free

  function joinWaitlist(e) {
    e.preventDefault()
    if (!email.includes('@')) return
    const entry = { email, note: note.slice(0, 200), at: todayKey(), interest: 'pro-launch' }
    update(s => ({ ...s, waitlist: [...(s.waitlist || []), entry] }))
    try {
      const local = JSON.parse(localStorage.getItem('apea-waitlist-log') || '[]')
      local.push({ ...entry, savedAt: new Date().toISOString() })
      localStorage.setItem('apea-waitlist-log', JSON.stringify(local))
    } catch { /* ignore */ }
    setJoined(true)
  }

  return (
    <div className="about-page">
      <PageHeader
        eyebrow="Pro value"
        title="Why this platform vs. PDFs alone"
        subtitle="Built from official APEA 2026 course manuals hosted for this cohort — structured for outcomes: readiness score, mocks, tracking, and recall."
      />

      <div className="card pro-hero">
        <p className="label">The problem</p>
        <h2 style={{ marginTop: 4 }}>Free materials are complete — but not organized for exam day</h2>
        <p className="muted" style={{ lineHeight: 1.65, maxWidth: 680 }}>
          You can download every manual. What you cannot get from a folder of PDFs is a <strong>readiness score</strong>, timed mocks at board pace,
          weak-area tracking across {totalQ} questions, or a single searchable path from Chapter 1 to the mock block. This hub wraps the same official content around those outcomes.
        </p>
        <p className="small muted" style={{ marginTop: 12, lineHeight: 1.5 }}>
          Social proof we can stand behind: content is sourced from the APEA 2026 FNP review manuals on this server — not third-party summaries. No fabricated testimonials during beta.
        </p>
      </div>

      <PlatformStats guide={guide} contentMeta={contentMeta} manualBank={manualBank} questionTotal={totalQ} />

      <div className="grid cols2" style={{ marginTop: 16 }}>
        <div className="card">
          <p className="label">{free.name}</p>
          <p className="price" style={{ fontSize: 28 }}>{free.priceLabel}</p>
          <p className="muted" style={{ lineHeight: 1.55 }}>{free.tagline}</p>
          <ul className="feature-list">{free.includes.map(f => <li key={f}>{f}</li>)}</ul>
        </div>
        <div className="card platform-card">
          <p className="label">{pro.name}</p>
          <p className="price" style={{ fontSize: 28 }}>{pro.priceLabel}</p>
          <p className="muted" style={{ lineHeight: 1.55 }}>{pro.tagline}</p>
          <ul className="feature-list">{pro.includes.map(f => <li key={f}>{f}</li>)}</ul>
          {BETA_OPEN && <p className="pill gold" style={{ marginTop: 12 }}>Beta: Pro features unlocked — {readiness}% readiness on your device</p>}
        </div>
      </div>

      <div className="card compare-table-wrap" style={{ marginTop: 16, overflowX: 'auto' }}>
        <p className="label">Compare</p>
        <h3 style={{ marginTop: 4 }}>Study guide PDFs vs. this platform</h3>
        <table className="compare-table">
          <thead>
            <tr><th>Capability</th><th>PDFs / self-study</th><th>This platform</th></tr>
          </thead>
          <tbody>
            {COMPARE_ROWS.map(row => (
              <tr key={row.feature}>
                <td>{row.feature}</td>
                <td className="muted">{row.pdf === true ? '✓' : row.pdf === false ? '—' : row.pdf}</td>
                <td><strong>{row.platform === true ? '✓' : row.platform}</strong></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card access-open" style={{ marginTop: 16 }}>
        <p className="label">What's included today</p>
        <ul className="feature-list">
          <li>{chapters} searchable guide chapters + {pearls ? `${pearls} clinical pearls` : 'clinical pearls'}</li>
          <li>22 course manuals (full text + PDF links)</li>
          <li>{totalQ} graded questions · {totalCards}+ flashcards · 1,720+ workbook drills</li>
          <li>Mock exams, 12-week path, planner, readiness report export</li>
        </ul>
        {BETA_OPEN && (
          <p className="muted" style={{ lineHeight: 1.6, marginBottom: 0 }}>
            <strong>Open beta:</strong> nothing is paywalled while we polish. Paid launch will bundle hosting, updates, and support — your progress export JSON still works if you switch devices.
          </p>
        )}
      </div>

      <div className="card waitlist-card" style={{ marginTop: 16 }}>
        <p className="label">Launch list</p>
        <h3 style={{ marginTop: 4 }}>Get one email when Pro pricing goes live</h3>
        <p className="muted" style={{ lineHeight: 1.6 }}>
          Optional. We store interest on <strong>this device</strong> (and in your progress backup) until we wire a real mailing list.
          Tell us what you want most: mocks, manuals search, or readiness tracking.
        </p>
        {joined ? (
          <p className="small" style={{ background: '#e6f5ec', padding: 12, borderRadius: 10, marginTop: 12 }}>
            <strong>You're on the list.</strong> We will only email about launch pricing — not daily marketing.
          </p>
        ) : (
          <form onSubmit={joinWaitlist}>
            <input type="email" required placeholder="you@school.edu" value={email} onChange={e => setEmail(e.target.value)} />
            <input type="text" placeholder="What matters most? (optional)" value={note} onChange={e => setNote(e.target.value)} style={{ marginTop: 10 }} />
            <button className="btn gold" type="submit" style={{ width: '100%', marginTop: 10 }}>Save my launch interest</button>
          </form>
        )}
      </div>
    </div>
  )
}
