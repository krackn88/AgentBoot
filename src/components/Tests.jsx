import React, { useMemo } from 'react'
import { Timer, Trophy, ClipboardList, Target, RotateCcw } from 'lucide-react'
import { shuffle } from '../lib/store'

const PASS_TARGET = 75

function gradable(guide) {
  return guide.chapters.flatMap(c => c.questions.filter(q => q.correctIndex != null && q.options.length >= 2).map(q => ({ ...q, chapter: c })))
}

// Round-robin across chapters so every mock covers the whole blueprint, not just the biggest chapter.
function balancedForms(qs, forms, seed) {
  const byCh = {}
  shuffle(qs, seed).forEach(q => { (byCh[q.chapterId] = byCh[q.chapterId] || []).push(q) })
  const out = Array.from({ length: forms }, () => [])
  let f = 0
  Object.values(byCh).forEach(list => list.forEach(q => { out[f % forms].push(q.id); f++ }))
  return out
}

export function buildTests(guide) {
  const qs = gradable(guide)
  const ids = qs.map(q => q.id)
  const forms = balancedForms(qs, 3, 2026)
  const tests = [
    { testId: 'aanp-full', kind: 'full', title: 'Full-Length AANP Simulation', blurb: 'Mirrors the real AANP FNP exam pacing: 150 questions in 3 hours (72 seconds each), drawn across every chapter.', count: Math.min(150, ids.length), minutes: 180, ids: shuffle(ids, 150).slice(0, 150) },
    { testId: 'ancc-full', kind: 'full', title: 'Full-Length ANCC Simulation', blurb: 'ANCC-length endurance run: up to 175 questions in 3.5 hours. Builds the stamina the real exam demands.', count: Math.min(175, ids.length), minutes: 210, ids: shuffle(ids, 175).slice(0, 175) },
    ...forms.map((f, i) => ({ testId: `mock-${i + 1}`, kind: 'mock', title: `Mock Board ${String.fromCharCode(65 + i)}`, blurb: `${f.length} questions, no overlap with the other mock boards, balanced across all chapters.`, count: f.length, minutes: Math.round(f.length * 1.2), ids: f })),
  ]
  const chapterTests = guide.chapters.map(c => {
    const cq = qs.filter(q => q.chapterId === c.id)
    return cq.length ? { testId: `ch-${c.id}`, kind: 'chapter', title: `${c.number}. ${c.shortTitle}`, count: cq.length, minutes: Math.max(5, Math.round(cq.length * 1.2)), ids: cq.map(q => q.id) } : null
  }).filter(Boolean)
  return { tests, chapterTests, total: ids.length }
}

function attemptsFor(store, testId) {
  return store.quizHistory.filter(h => h.testId === testId)
}
const pct = h => (h.graded ? Math.round(h.correct / h.graded * 100) : 0)

export default function Tests({ guide, store, onStart }) {
  const { tests, chapterTests, total } = useMemo(() => buildTests(guide), [guide])
  const history = store.quizHistory.filter(h => h.testId).slice(-8).reverse()
  const fullScores = store.quizHistory.filter(h => h.testId && !h.testId.startsWith('ch-')).map(pct)
  const best = fullScores.length ? Math.max(...fullScores) : null
  const last3 = fullScores.slice(-3)
  const trend = last3.length ? Math.round(last3.reduce((a, b) => a + b, 0) / last3.length) : null

  const start = t => onStart({ mode: 'exam', chapterId: 'all', count: t.count, minutes: t.minutes, ids: t.ids, testId: t.testId, title: t.title })

  return (
    <div>
      <div className="manual-hero compact">
        <div>
          <p className="eyebrow">Testing center</p>
          <h1>Mock boards, under real exam conditions</h1>
          <p>Every test is timed and graded against the APEA Answer Key, with a full rationale review afterward. Aim for a consistent {PASS_TARGET}%+ before exam day.</p>
        </div>
        <div className="source-proof">
          <span><strong>{total}</strong> graded questions</span>
          <span><strong>{best ?? '—'}{best != null ? '%' : ''}</strong> best mock score</span>
          <span><strong>{trend ?? '—'}{trend != null ? '%' : ''}</strong> recent average</span>
        </div>
      </div>

      {trend != null && (
        <div className={`card readiness-banner ${trend >= PASS_TARGET ? 'good' : trend >= 65 ? 'close' : 'low'}`}>
          <Target size={20} />
          <div><strong>{trend >= PASS_TARGET ? 'On track to pass.' : trend >= 65 ? 'Close to passing range.' : 'Not exam-ready yet.'}</strong>{' '}
            Your recent mock average is {trend}%. {trend >= PASS_TARGET ? 'Keep taking a full-length test each week to stay sharp.' : `Review the rationales from your misses and retake a mock board until you hold ${PASS_TARGET}%+.`}</div>
        </div>
      )}

      <div className="section-title"><div><p className="eyebrow">Full-length and mock boards</p><h2>Exam simulations</h2></div></div>
      <div className="test-grid">
        {tests.map(t => {
          const a = attemptsFor(store, t.testId)
          const bestT = a.length ? Math.max(...a.map(pct)) : null
          return (
            <article key={t.testId} className={`test-card ${t.kind}`}>
              <div className="test-top">
                {t.kind === 'full' ? <Trophy size={20} /> : <ClipboardList size={20} />}
                {bestT != null && <span className={`score-chip ${bestT >= PASS_TARGET ? 'good' : bestT >= 65 ? 'close' : 'low'}`}>Best {bestT}%</span>}
              </div>
              <h3>{t.title}</h3>
              <p>{t.blurb}</p>
              <div className="test-meta"><span><ClipboardList size={14} /> {t.count} questions</span><span><Timer size={14} /> {t.minutes} min</span>{a.length > 0 && <span><RotateCcw size={14} /> {a.length} attempt{a.length > 1 ? 's' : ''}</span>}</div>
              <button className="btn" onClick={() => start(t)}>{a.length ? 'Retake test' : 'Start test'}</button>
            </article>
          )
        })}
      </div>

      <div className="section-title"><div><p className="eyebrow">Targeted practice</p><h2>Chapter tests</h2></div><p className="muted">Every graded question in the chapter, timed at 72 seconds each.</p></div>
      <div className="card" style={{ padding: 0 }}>
        {chapterTests.map(t => {
          const a = attemptsFor(store, t.testId)
          const bestT = a.length ? Math.max(...a.map(pct)) : null
          return (
            <div key={t.testId} className="chapter-test-row">
              <div style={{ flex: 1 }}><strong>{t.title}</strong><p className="small muted" style={{ margin: '2px 0 0' }}>{t.count} questions · {t.minutes} min</p></div>
              {bestT != null ? <span className={`score-chip ${bestT >= PASS_TARGET ? 'good' : bestT >= 65 ? 'close' : 'low'}`}>{bestT}%</span> : <span className="small muted">Not taken</span>}
              <button className="btn ghost" onClick={() => start(t)}>{a.length ? 'Retake' : 'Start'}</button>
            </div>
          )
        })}
      </div>

      {history.length > 0 && <>
        <div className="section-title"><div><p className="eyebrow">Your record</p><h2>Recent test results</h2></div></div>
        <div className="card" style={{ padding: 0 }}>
          {history.map((h, i) => (
            <div key={i} className="chapter-test-row">
              <div style={{ flex: 1 }}><strong>{h.title || h.testId}</strong><p className="small muted" style={{ margin: '2px 0 0' }}>{h.date} · {h.correct}/{h.graded} correct · {Math.floor(h.seconds / 60)} min</p></div>
              <span className={`score-chip ${pct(h) >= PASS_TARGET ? 'good' : pct(h) >= 65 ? 'close' : 'low'}`}>{pct(h)}%</span>
            </div>
          ))}
        </div>
      </>}
    </div>
  )
}
