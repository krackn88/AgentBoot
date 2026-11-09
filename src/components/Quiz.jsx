import React, { useMemo, useState, useEffect } from 'react'
import { shuffle, todayKey, bumpDaily } from '../lib/store'
import { PageHeader } from './AppShell.jsx'
import { gradable } from '../lib/questions'

export default function Quiz({ guide, store, update, preset, onDone, questionPool }) {
  const allQ = useMemo(
    () => questionPool || guide.chapters.flatMap(c => c.questions.map(q => ({ ...q, chapterTitle: c.shortTitle }))),
    [guide, questionPool]
  )
  const [setup, setSetup] = useState(!preset)
  const [mode, setMode] = useState(preset?.mode || 'practice')
  const [chapterId, setChapterId] = useState(preset?.chapterId || 'all')
  const [count, setCount] = useState(preset?.mode === 'exam' ? 50 : 15)
  const [session, setSession] = useState(null)
  const [idx, setIdx] = useState(0); const [picked, setPicked] = useState({}); const [flags, setFlags] = useState({})
  const [revealed, setRevealed] = useState({}); const [seconds, setSeconds] = useState(0); const [result, setResult] = useState(null)

  const limit = (preset?.minutes ?? 60) * 60
  useEffect(() => { if (preset) start(preset.mode, preset.chapterId, preset.count ?? (preset.mode === 'exam' ? 50 : 15), preset.seed, preset.ids) }, [])
  useEffect(() => {
    if (!session || result) return
    const t = setInterval(() => setSeconds(s => s + 1), 1000); return () => clearInterval(t)
  }, [session, result])
  useEffect(() => { if (session?.mode === 'exam' && seconds >= limit && !result) finish() }, [seconds, session, result])
  // Keyboard: 1-4 / A-D pick, Enter checks in practice, arrows navigate
  useEffect(() => {
    if (!session || result) return
    function onKey(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return
      const q = session.questions[idx]; if (!q) return
      const n = ['1','2','3','4','5','6'].indexOf(e.key); const l = ['a','b','c','d','e','f'].indexOf(e.key.toLowerCase())
      const pick = n >= 0 ? n : l
      if (pick >= 0 && q.options[pick] != null && !(session.mode === 'practice' && revealed[q.id])) setPicked(p => ({ ...p, [q.id]: pick }))
      if (e.key === 'Enter' && session.mode === 'practice' && !revealed[q.id] && picked[q.id] != null) setRevealed(r => ({ ...r, [q.id]: true }))
      if (e.key === 'ArrowRight' && idx < session.questions.length - 1) setIdx(idx + 1)
      if (e.key === 'ArrowLeft' && idx > 0) setIdx(idx - 1)
      if (e.key === 'F' || (e.key === 'f' && !(q.options.length > 5))) setFlags(f => ({ ...f, [q.id]: !f[q.id] }))
    }
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey)
  }, [session, result, idx, picked, revealed])

  function pool(m, ch) {
    let p = ch === 'all' ? allQ : allQ.filter(q => q.chapterId === ch)
    if (m === 'exam' || m === 'mixed') p = p.filter(q => q.correctIndex != null && q.options.length >= 2)
    if (m === 'missed') p = p.filter(q => store.answers[q.id] && !store.answers[q.id].correct)
    return p
  }
  function start(m = mode, ch = chapterId, n = count, seed, ids) {
    const p = ids ? ids.map(id => allQ.find(q => q.id === id)).filter(Boolean) : shuffle(pool(m, ch), seed).slice(0, n)
    if (!p.length) return alert('No questions in that set yet — answer some practice questions first (Missed set builds from your attempts).')
    setSession({ questions: p, mode: m, chapterId: ch, title: preset?.title }); setIdx(0); setPicked({}); setFlags({}); setRevealed({}); setSeconds(0); setResult(null); setSetup(false)
  }
  function finish() {
    const qs = session.questions
    let correct = 0, graded = 0
    const byChapter = {}
    qs.forEach(q => {
      const a = picked[q.id]; const isG = q.correctIndex != null && q.options.length >= 2
      if (isG) { graded++; const ok = a === q.correctIndex; if (ok) correct++; byChapter[q.chapterTitle] = byChapter[q.chapterTitle] || { t: 0, c: 0 }; byChapter[q.chapterTitle].t++; if (ok) byChapter[q.chapterTitle].c++ }
    })
    const res = { correct, graded, total: qs.length, byChapter, seconds, date: todayKey(), mode: session.mode, testId: preset?.testId, title: session.title }
    setResult(res)
    update(s => bumpDaily({
      ...s,
      answers: { ...s.answers, ...Object.fromEntries(qs.filter(q => q.correctIndex != null).map(q => [q.id, { correct: picked[q.id] === q.correctIndex, chosen: picked[q.id], chapterId: q.chapterId }])) },
      quizHistory: [...s.quizHistory, res], studyDates: [...new Set([...s.studyDates, todayKey()])],
    }, 'answered', qs.length))
    onDone?.(res)
  }

  const poolSize = gradable(allQ).length
  const manualInPool = allQ.filter(q => q.source === 'manual' && q.correctIndex != null).length

  if (setup) return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      <PageHeader eyebrow="Question bank" title="Practice & exam simulator" subtitle={`${poolSize} graded items (${manualInPool} from course-manual slides). Keyboard: 1–4 answer · Enter check · ←/→ navigate · F flag.`} />
      <div className="card">
        <p className="label">Mode</p>
        {[['practice', 'Practice — instant rationale after each question'], ['mixed', 'Mixed quiz — answers at the end'], ['exam', 'Timed exam simulator — 50 questions, 60 minutes, flag & review'], ['missed', 'Missed questions — only questions you have gotten wrong']].map(([v, l]) => (
          <label key={v} style={{ display: 'block', padding: '8px 0' }}><input type="radio" name="m" checked={mode === v} onChange={() => { setMode(v); if (v === 'exam') setCount(50) }} /> {l}</label>))}
        <p className="label" style={{ marginTop: 14 }}>Chapter</p>
        <select value={chapterId} onChange={e => setChapterId(e.target.value)}>
          <option value="all">All chapters (mixed)</option>
          {guide.chapters.filter(c => c.questions.length).map(c => <option key={c.id} value={c.id}>{c.number}. {c.shortTitle} ({c.questions.length})</option>)}
        </select>
        {mode !== 'exam' && <><p className="label" style={{ marginTop: 14 }}>Questions: {count}</p>
          <input type="range" min={5} max={50} step={5} value={count} onChange={e => setCount(Number(e.target.value))} style={{ width: '100%' }} /></>}
        <button className="btn" style={{ marginTop: 16 }} onClick={() => start()}>Start →</button>
      </div>
    </div>
  )
  if (!session) return null
  if (result) {
    const pct = result.graded ? Math.round(result.correct / result.graded * 100) : 0
    return (
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <h1>{pct >= 75 ? 'Board-ready pace' : pct >= 60 ? 'Close to passing range' : 'Review rationales and retry'}</h1>
        <p className="muted" style={{ marginTop: -8 }}>{session.title || 'Practice session'} · {result.mode} mode</p>
        <div className="grid cols3">
          <div className="card"><p className="label">Score</p><p className="stat">{pct}%</p><p className="small muted">{result.correct}/{result.graded} graded correct</p></div>
          <div className="card"><p className="label">Time</p><p className="stat">{Math.floor(result.seconds / 60)}:{String(result.seconds % 60).padStart(2, '0')}</p><p className="small muted">{result.graded ? Math.round(result.seconds / result.graded) : 0}s per question (AANP pace: 72s)</p></div>
          <div className="card"><p className="label">Questions</p><p className="stat">{result.total}</p><p className="small muted">{result.mode} mode</p></div>
        </div>
        <div className="card" style={{ marginTop: 16 }}><h3 style={{ marginTop: 0 }}>By chapter</h3>
          {Object.entries(result.byChapter).map(([k, v]) => (
            <div key={k} style={{ margin: '10px 0' }}><div style={{ display: 'flex', justifyContent: 'space-between' }}><span>{k}</span><strong>{v.c}/{v.t}</strong></div>
              <div className="bar"><i style={{ width: `${v.t ? v.c / v.t * 100 : 0}%` }} /></div></div>))}
        </div>
        <h3>Review every question</h3>
        {session.questions.map((q, i) => (
          <div className="card" key={q.id} style={{ margin: '10px 0' }}>
            <p className="label">{q.chapterTitle} · Q{i + 1}</p><p><strong>{q.stem}</strong></p>
            {q.options.map((o, j) => <p key={j} className="small" style={{ color: j === q.correctIndex ? 'var(--green)' : picked[q.id] === j ? 'var(--red)' : 'inherit', fontWeight: j === q.correctIndex ? 700 : 400 }}>{String.fromCharCode(65 + j)}. {o}{j === q.correctIndex ? ' ✓' : picked[q.id] === j ? ' ✗ your answer' : ''}</p>)}
            {q.explanation && <p className="small" style={{ background: '#f2f6fb', padding: 10, borderRadius: 8 }}><strong>Rationale:</strong> {q.explanation}<br /><span className="muted">Source: {q.source === 'manual' ? 'Course manual slide' : 'Answer Key'}</span></p>}
          </div>))}
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}><button className="btn" onClick={() => { setSetup(true); setSession(null); setResult(null) }}>New quiz</button>
          <button className="btn ghost" onClick={() => start('missed', 'all', 25)}>Retry missed only</button></div>
      </div>
    )
  }
  const q = session.questions[idx]; const isGraded = q.correctIndex != null && q.options.length >= 2
  const showAns = session.mode === 'practice' && revealed[q.id]
  const timeLeft = session.mode === 'exam' ? limit - seconds : null
  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <p className="label">{session.title ? `${session.title} · ` : ''}Question {idx + 1} / {session.questions.length} · {q.chapterTitle}{q.source === 'manual' && <span className="pill" style={{ marginLeft: 6 }}>Manual slide</span>}</p>
        <p className="label">{session.mode === 'exam' ? `⏱ ${Math.max(0, Math.floor(timeLeft / 60))}:${String(Math.max(0, timeLeft % 60)).padStart(2, '0')} left` : `⏱ ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`}</p>
      </div>
      <div className="bar"><i style={{ width: `${(idx + 1) / session.questions.length * 100}%` }} /></div>
      <div className="card" style={{ marginTop: 16 }}>
        <p style={{ fontSize: 18, lineHeight: 1.6 }}><strong>{q.stem}</strong></p>
        {q.options.length >= 2 ? q.options.map((o, j) => {
          let cls = 'opt' + (picked[q.id] === j ? ' sel' : '')
          if (showAns) cls = 'opt' + (j === q.correctIndex ? ' right' : picked[q.id] === j ? ' wrong' : '')
          return <button key={j} className={cls} disabled={showAns} onClick={() => setPicked(p => ({ ...p, [q.id]: j }))}><strong>{String.fromCharCode(65 + j)}.</strong> {o}</button>
        }) : <p className="muted">Recall question — think of the answer, then reveal the rationale below.</p>}
        {session.mode === 'practice' && !showAns && <button className="btn" disabled={picked[q.id] == null && q.options.length >= 2} onClick={() => setRevealed(r => ({ ...r, [q.id]: true }))}>Check answer</button>}
        {showAns && <div style={{ background: '#f2f6fb', padding: 14, borderRadius: 10, marginTop: 10 }}>
          <strong>{!isGraded ? 'Answer & rationale' : picked[q.id] === q.correctIndex ? '✓ Correct' : '✗ Not quite'}:</strong> {q.explanation || 'See the chapter for the teaching point behind this question.'}
          <p className="small muted" style={{ margin: '10px 0 0' }}>Source: {q.source === 'manual' ? 'Course manual slide MCQ (keyed + override when needed)' : 'Study guide Answer Key'}</p>
        </div>}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
        <button className="btn ghost" disabled={idx === 0} onClick={() => setIdx(idx - 1)}>← Prev</button>
        <button className="btn ghost" onClick={() => setFlags(f => ({ ...f, [q.id]: !f[q.id] }))}>{flags[q.id] ? '⚑ Flagged' : 'Flag for review'}</button>
        {idx < session.questions.length - 1 ? <button className="btn" onClick={() => setIdx(idx + 1)}>Next →</button>
          : <button className="btn gold" onClick={() => { const un = session.questions.filter(q => picked[q.id] == null && q.options.length >= 2).length; if (un && !confirm(`You still have ${un} unanswered question${un>1?'s':''}. Submit anyway?`)) return; finish() }}>Finish & grade →</button>}
      </div>
      {(session.mode !== 'practice') && <div className="card" style={{ marginTop: 16 }}><p className="label">Question navigator</p>
        <div className="qgrid">{session.questions.map((qq, i) => <button key={qq.id} className={`${picked[qq.id] != null ? 'ans' : ''} ${flags[qq.id] ? 'flag' : ''}`} onClick={() => setIdx(i)}>{i + 1}</button>)}</div>
        <button className="btn gold" style={{ marginTop: 14 }} onClick={() => { const un = session.questions.filter(q => picked[q.id] == null).length; if (un && !confirm(`You still have ${un} unanswered question${un>1?'s':''}. Submit anyway?`)) return; finish() }}>Submit exam</button></div>}
    </div>
  )
}
