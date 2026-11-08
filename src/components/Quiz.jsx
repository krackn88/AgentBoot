import React, { useMemo, useState, useEffect } from 'react'
import { shuffle, todayKey } from '../lib/store'

export default function Quiz({ guide, store, update, preset, onDone }) {
  const allQ = useMemo(() => guide.chapters.flatMap(c => c.questions.map(q => ({ ...q, chapterTitle: c.shortTitle }))), [guide])
  const [setup, setSetup] = useState(!preset)
  const [mode, setMode] = useState(preset?.mode || 'practice')
  const [chapterId, setChapterId] = useState(preset?.chapterId || 'all')
  const [count, setCount] = useState(preset?.mode === 'exam' ? 50 : 15)
  const [session, setSession] = useState(null)
  const [idx, setIdx] = useState(0); const [picked, setPicked] = useState({}); const [flags, setFlags] = useState({})
  const [revealed, setRevealed] = useState({}); const [seconds, setSeconds] = useState(0); const [result, setResult] = useState(null)

  useEffect(() => { if (preset) start(preset.mode, preset.chapterId, preset.mode === 'exam' ? 50 : 15) }, [])
  useEffect(() => {
    if (!session || result) return
    const t = setInterval(() => setSeconds(s => s + 1), 1000); return () => clearInterval(t)
  }, [session, result])

  function pool(m, ch) {
    let p = ch === 'all' ? allQ : allQ.filter(q => q.chapterId === ch)
    if (m === 'exam' || m === 'mixed') p = p.filter(q => q.correctIndex != null && q.options.length >= 2)
    if (m === 'missed') p = p.filter(q => store.answers[q.id] && !store.answers[q.id].correct)
    return p
  }
  function start(m = mode, ch = chapterId, n = count) {
    const p = shuffle(pool(m, ch)).slice(0, n)
    if (!p.length) return alert('No questions in that set yet — answer some practice questions first (Missed set builds from your attempts).')
    setSession({ questions: p, mode: m, chapterId: ch }); setIdx(0); setPicked({}); setFlags({}); setRevealed({}); setSeconds(0); setResult(null); setSetup(false)
  }
  function finish() {
    const qs = session.questions
    let correct = 0, graded = 0
    const byChapter = {}
    qs.forEach(q => {
      const a = picked[q.id]; const isG = q.correctIndex != null && q.options.length >= 2
      if (isG) { graded++; const ok = a === q.correctIndex; if (ok) correct++; byChapter[q.chapterTitle] = byChapter[q.chapterTitle] || { t: 0, c: 0 }; byChapter[q.chapterTitle].t++; if (ok) byChapter[q.chapterTitle].c++ }
    })
    const res = { correct, graded, total: qs.length, byChapter, seconds, date: todayKey(), mode: session.mode }
    setResult(res)
    update(s => ({
      ...s,
      answers: { ...s.answers, ...Object.fromEntries(qs.filter(q => q.correctIndex != null).map(q => [q.id, { correct: picked[q.id] === q.correctIndex, chosen: picked[q.id] }])) },
      quizHistory: [...s.quizHistory, res], studyDates: [...new Set([...s.studyDates, todayKey()])],
    }))
    onDone?.(res)
  }

  if (setup) return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      <h1>Practice & Exam Simulator</h1>
      <p className="muted">All {allQ.length} questions come straight from your APEA manual chapters, graded against the Answer Key with rationales. Exam mode mirrors AANP pacing (150 questions / 3 hours ≈ 72 seconds per question).</p>
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
        <h1>{pct >= 75 ? 'Board-ready pace 🎉' : pct >= 60 ? 'Getting close — keep drilling' : 'Keep going — review and retry'}</h1>
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
            {q.explanation && <p className="small" style={{ background: '#f2f6fb', padding: 10, borderRadius: 8 }}><strong>Rationale:</strong> {q.explanation}</p>}
          </div>))}
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}><button className="btn" onClick={() => { setSetup(true); setSession(null); setResult(null) }}>New quiz</button>
          <button className="btn ghost" onClick={() => start('missed', 'all', 25)}>Retry missed only</button></div>
      </div>
    )
  }
  const q = session.questions[idx]; const isGraded = q.correctIndex != null && q.options.length >= 2
  const showAns = session.mode === 'practice' && revealed[q.id]
  const timeLeft = session.mode === 'exam' ? 3600 - seconds : null
  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <p className="label">Question {idx + 1} / {session.questions.length} · {q.chapterTitle}</p>
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
          <strong>{!isGraded ? 'Answer & rationale' : picked[q.id] === q.correctIndex ? '✓ Correct' : '✗ Not quite'}:</strong> {q.explanation || 'See the chapter for the teaching point behind this question.'}</div>}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
        <button className="btn ghost" disabled={idx === 0} onClick={() => setIdx(idx - 1)}>← Prev</button>
        <button className="btn ghost" onClick={() => setFlags(f => ({ ...f, [q.id]: !f[q.id] }))}>{flags[q.id] ? '⚑ Flagged' : 'Flag for review'}</button>
        {idx < session.questions.length - 1 ? <button className="btn" onClick={() => setIdx(idx + 1)}>Next →</button>
          : <button className="btn gold" onClick={finish}>Finish & grade →</button>}
      </div>
      {(session.mode !== 'practice') && <div className="card" style={{ marginTop: 16 }}><p className="label">Question navigator</p>
        <div className="qgrid">{session.questions.map((qq, i) => <button key={qq.id} className={`${picked[qq.id] != null ? 'ans' : ''} ${flags[qq.id] ? 'flag' : ''}`} onClick={() => setIdx(i)}>{i + 1}</button>)}</div>
        <button className="btn gold" style={{ marginTop: 14 }} onClick={finish}>Submit exam</button></div>}
    </div>
  )
}
