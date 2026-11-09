import React, { useMemo } from 'react'
import { Timer, Trophy, ClipboardList, Target, RotateCcw, Layers } from 'lucide-react'
import { PageHeader } from './AppShell.jsx'
import { shuffle } from '../lib/store'

const PASS_TARGET = 75

function gradableFromPool(pool) {
  return pool.filter(q => q.correctIndex != null && q.options.length >= 2).map(q => ({
    ...q,
    chapter: { id: q.chapterId, shortTitle: q.chapterTitle || q.chapterId },
  }))
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

export function buildTests(guide, questionPool) {
  const pool = questionPool || guide.chapters.flatMap(c => c.questions.map(q => ({ ...q, chapterTitle: c.shortTitle, chapterId: c.id })))
  const qs = gradableFromPool(pool)
  const guideQs = gradableFromPool(pool.filter(q => q.source !== 'manual'))
  const manualQs = gradableFromPool(pool.filter(q => q.source === 'manual'))
  const ids = qs.map(q => q.id)
  const guideIds = guideQs.map(q => q.id)
  const manualIds = manualQs.map(q => q.id)
  const forms = balancedForms(guideQs, 3, 2026)
  const manualForms = balancedForms(manualQs, 3, 9026)
  const tests = [
    { testId: 'aanp-full', kind: 'full', title: 'Full-Length AANP Simulation', blurb: 'Mirrors the real AANP FNP exam pacing: 150 questions in 3 hours (72 seconds each), drawn across every chapter.', count: Math.min(150, guideIds.length), minutes: 180, ids: shuffle(guideIds, 150).slice(0, 150) },
    { testId: 'ancc-full', kind: 'full', title: 'Full-Length ANCC Simulation', blurb: 'ANCC-length endurance run: up to 175 questions in 3.5 hours. Builds the stamina the real exam demands.', count: Math.min(175, guideIds.length), minutes: 210, ids: shuffle(guideIds, 175).slice(0, 175) },
    ...forms.map((f, i) => ({ testId: `mock-${i + 1}`, kind: 'mock', title: `Mock Board ${String.fromCharCode(65 + i)}`, blurb: `${f.length} study-guide questions, balanced across all chapters (Answer Key).`, count: f.length, minutes: Math.round(f.length * 1.2), ids: f })),
    ...manualForms.map((f, i) => ({
      testId: `manual-mock-${i + 1}`,
      kind: 'mock',
      title: `Course Manual Mock ${String.fromCharCode(65 + i)}`,
      blurb: `${f.length} unique slide MCQs from the original APEA manuals (auto-graded where slide context allows; curated overrides for high-yield items).`,
      count: f.length,
      minutes: Math.round(f.length * 1.2),
      ids: f,
    })),
    {
      testId: 'combo-mega',
      kind: 'full',
      title: 'Combo Board (Guide + Manual)',
      blurb: `Blended ${Math.min(120, ids.length)}-question mix from both banks when you need fresh stems.`,
      count: Math.min(120, ids.length),
      minutes: 150,
      ids: shuffle(ids, 120).slice(0, 120),
    },
  ]
  const chapterTests = guide.chapters.map(c => {
    const cq = qs.filter(q => q.chapterId === c.id)
    return cq.length ? { testId: `ch-${c.id}`, kind: 'chapter', title: `${c.number}. ${c.shortTitle}`, count: cq.length, minutes: Math.max(5, Math.round(cq.length * 1.2)), ids: cq.map(q => q.id) } : null
  }).filter(Boolean)
  return { tests, chapterTests, total: ids.length, guideTotal: guideIds.length, manualTotal: manualIds.length }
}

function attemptsFor(store, testId) {
  return store.quizHistory.filter(h => h.testId === testId)
}
const pct = h => (h.graded ? Math.round(h.correct / h.graded * 100) : 0)

export default function Tests({ guide, store, onStart, questionPool }) {
  const { tests, chapterTests, total, guideTotal, manualTotal } = useMemo(() => buildTests(guide, questionPool), [guide, questionPool])
  const history = store.quizHistory.filter(h => h.testId).slice(-8).reverse()
  const fullScores = store.quizHistory.filter(h => h.testId && !h.testId.startsWith('ch-')).map(pct)
  const best = fullScores.length ? Math.max(...fullScores) : null
  const last3 = fullScores.slice(-3)
  const trend = last3.length ? Math.round(last3.reduce((a, b) => a + b, 0) / last3.length) : null

  const start = t => onStart({ mode: 'exam', chapterId: 'all', count: t.count, minutes: t.minutes, ids: t.ids, testId: t.testId, title: t.title })
  const boardTests = tests.filter(t => !t.testId.startsWith('manual-'))
  const manualTests = tests.filter(t => t.testId.startsWith('manual-'))

  return (
    <div>
      <PageHeader eyebrow="Testing center" title="Mock boards under exam conditions" subtitle="Timed, graded, and rationales after every run. Aim for 75%+ on full-length simulations before exam day." />
      <div className="manual-hero compact">
        <div>
          <p className="eyebrow">Testing center</p>
          <h1>Mock boards, under real exam conditions</h1>
          <p>Every test is timed and graded against the APEA Answer Key, with a full rationale review afterward. Aim for a consistent {PASS_TARGET}%+ before exam day.</p>
        </div>
        <div className="source-proof">
          <span><strong>{total}</strong> graded ({guideTotal} guide + {manualTotal} manual)</span>
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

      <div className="section-title"><div><p className="eyebrow">Answer Key bank</p><h2>Full-length & study-guide mocks</h2></div></div>
      <div className="test-grid">
        {boardTests.filter(t => t.kind === 'full' || t.testId.startsWith('mock-') || t.testId === 'combo-mega').map(t => {
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

      {manualTests.length > 0 && (
        <>
          <div className="section-title" style={{ marginTop: 28 }}><div><p className="eyebrow">Course manuals</p><h2>Slide MCQ mocks (unique bank)</h2></div><p className="muted">Fresh stems from the original APEA slides — does not overlap the study-guide Answer Key mocks.</p></div>
          <div className="test-grid">
            {manualTests.map(t => {
              const a = attemptsFor(store, t.testId)
              const bestT = a.length ? Math.max(...a.map(pct)) : null
              return (
                <article key={t.testId} className="test-card manual-mock">
                  <div className="test-top"><Layers size={20} />{bestT != null && <span className={`score-chip ${bestT >= PASS_TARGET ? 'good' : bestT >= 65 ? 'close' : 'low'}`}>Best {bestT}%</span>}</div>
                  <h3>{t.title}</h3><p>{t.blurb}</p>
                  <div className="test-meta"><span><ClipboardList size={14} /> {t.count} questions</span><span><Timer size={14} /> {t.minutes} min</span></div>
                  <button className="btn" onClick={() => start(t)}>{a.length ? 'Retake test' : 'Start test'}</button>
                </article>
              )
            })}
          </div>
        </>
      )}

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
