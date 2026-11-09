import React, { useMemo } from 'react'
import { Timer, Trophy, ClipboardList, Target, RotateCcw, Layers, ShieldCheck } from 'lucide-react'
import { PageHeader } from './AppShell.jsx'
import { shuffle } from '../lib/store'
import { examUsable, examPool } from '../lib/examPool'
export { examUsable }

const PASS_TARGET = 75


/** Allocate `total` slots across chapters proportionally, never exceeding supply. */
function allocate(byChapter, total, seed) {
  const ids = Object.keys(byChapter)
  const supply = Object.fromEntries(ids.map(id => [id, byChapter[id].length]))
  const totalSupply = ids.reduce((a, id) => a + supply[id], 0)
  if (!totalSupply) return {}

  const taken = Object.fromEntries(ids.map(id => [id, 0]))
  let remaining = Math.min(total, totalSupply)

  ids.forEach(id => {
    const share = Math.floor((supply[id] / totalSupply) * total)
    const give = Math.min(share, supply[id])
    taken[id] = give
    remaining -= give
  })
  while (remaining > 0) {
    const candidates = ids
      .filter(id => taken[id] < supply[id])
      .sort((a, b) => supply[a] / (taken[a] + 1) - supply[b] / (taken[b] + 1))
    if (!candidates.length) break
    taken[candidates[0]] += 1
    remaining -= 1
  }

  const chosen = {}
  Object.entries(taken).forEach(([id, n]) => {
    if (n > 0) chosen[id] = shuffle(byChapter[id], seed + id.length).slice(0, n).map(q => q.id)
  })
  return chosen
}

function groupByChapter(qs) {
  const by = {}
  qs.forEach(q => { (by[q.chapterId] = by[q.chapterId] || []).push(q) })
  return by
}

/**
 * Build the exam catalog.
 *
 * Full-lengths deliberately consume the verified manual bank as well as the study
 * guide. Drawing a 150-item form from the 314 guide items alone meant ~50% of the
 * questions overlapped the smaller practice mocks — someone who took Mock A then a
 * full-length saw half of it twice.
 */
export function buildTests(guide, questionPool) {
  const pool = questionPool || guide.chapters.flatMap(c =>
    c.questions.map(q => ({ ...q, chapterTitle: c.shortTitle, chapterId: c.id })),
  )
  const qs = examPool(pool)
  const guideQs = examPool(pool.filter(q => q.source !== 'manual'))
  const manualQs = examPool(pool.filter(q => q.source === 'manual'))

  const ids = qs.map(q => q.id)
  const guideIds = guideQs.map(q => q.id)
  const manualIds = manualQs.map(q => q.id)

  const aanpIds = Object.values(allocate(groupByChapter(qs), 150, 2026)).flat()
  const anccIds = Object.values(allocate(groupByChapter(qs), 175, 4117)).flat()
  const comboCapped = Math.min(120, ids.length)

  const manualForms = [1, 2, 3].map(i => ({
    form: i,
    ids: Object.values(
      allocate(groupByChapter(manualQs), Math.floor(manualQs.length / 3), 9026 + i),
    ).flat(),
  }))

  const tests = [
    {
      testId: 'aanp-full',
      kind: 'full',
      title: 'Full-Length AANP Simulation',
      blurb: 'Real AANP pacing: 150 questions in 3 hours (72 s each), weighted across every chapter and drawn from both verified banks.',
      count: aanpIds.length,
      minutes: 180,
      ids: aanpIds,
    },
    {
      testId: 'ancc-full',
      kind: 'full',
      title: 'Full-Length ANCC Simulation',
      blurb: 'ANCC-length endurance run: 175 questions in 3.5 hours. Tests stamina the way the real exam does.',
      count: anccIds.length,
      minutes: 210,
      ids: anccIds,
    },
    {
      testId: 'combo-mega',
      kind: 'full',
      title: 'Combo Board (Guide + Manual)',
      blurb: `Blended ${comboCapped}-question mix from both banks when you need fresh stems. Duplicate and unverified items are excluded.`,
      count: comboCapped,
      minutes: 150,
      ids: shuffle(ids, 120).slice(0, comboCapped),
    },
    ...manualForms.map(({ form, ids: f }) => ({
      testId: `manual-mock-${form}`,
      kind: 'mock',
      title: `Course Manual Mock ${String.fromCharCode(64 + form)}`,
      blurb: `${f.length} verified slide MCQs from the original APEA manuals — answers cross-walked to hand-curated overrides or the study-guide Answer Key.`,
      count: f.length,
      minutes: Math.round(f.length * 1.2),
      ids: f,
    })),
  ]

  const chapterTests = guide.chapters
    .map(c => {
      const cq = qs.filter(q => q.chapterId === c.id)
      return cq.length
        ? {
            testId: `ch-${c.id}`,
            kind: 'chapter',
            title: `${c.number}. ${c.shortTitle}`,
            count: cq.length,
            minutes: Math.max(5, Math.round(cq.length * 1.2)),
            ids: cq.map(q => q.id),
          }
        : null
    })
    .filter(Boolean)

  return {
    tests,
    chapterTests,
    total: ids.length,
    guideTotal: guideIds.length,
    manualTotal: manualIds.length,
  }
}

function attemptsFor(store, testId) {
  return store.quizHistory.filter(h => h.testId === testId)
}
const pct = h => (h.graded ? Math.round((h.correct / h.graded) * 100) : 0)

export default function Tests({ guide, store, onStart, questionPool }) {
  const { tests, chapterTests, total, guideTotal, manualTotal } = useMemo(
    () => buildTests(guide, questionPool),
    [guide, questionPool],
  )
  const history = store.quizHistory.filter(h => h.testId).slice(-8).reverse()
  const fullScores = store.quizHistory.filter(h => h.testId && !h.testId.startsWith('ch-')).map(pct)
  const best = fullScores.length ? Math.max(...fullScores) : null
  const last3 = fullScores.slice(-3)
  const trend = last3.length ? Math.round(last3.reduce((a, b) => a + b, 0) / last3.length) : null

  const start = t => onStart({ mode: 'exam', chapterId: 'all', count: t.count, minutes: t.minutes, ids: t.ids, testId: t.testId, title: t.title })
  const fullTests = tests.filter(t => t.kind === 'full')
  const manualTests = tests.filter(t => t.testId.startsWith('manual-'))
  const noMocksYet = fullScores.length === 0

  return (
    <div>
      <PageHeader
        eyebrow="Mock exams"
        title="Timed boards with rationales after every run"
        subtitle={`Aim for ${PASS_TARGET}%+ on full-length simulations before exam day. Every item in a full-length has a verified answer key.`}
        actions={(
          <div className="source-proof source-proof-inline">
            <span><strong>{total}</strong> exam-ready Q</span>
            <span><strong>{best ?? '—'}{best != null ? '%' : ''}</strong> best</span>
            <span><strong>{trend ?? '—'}{trend != null ? '%' : ''}</strong> recent avg</span>
          </div>
        )}
      />

      {noMocksYet && (
        <div className="card empty-cta">
          <h3 style={{ marginTop: 0 }}>No mock exams yet</h3>
          <p className="muted" style={{ lineHeight: 1.6, marginBottom: 14 }}>
            Start with a full-length AANP simulation — timer on, rationales after. One full-length per week beats re-reading PDFs.
          </p>
          <button type="button" className="btn gold" onClick={() => start(fullTests.find(t => t.testId === 'aanp-full') || tests[0])}>
            Start AANP full-length mock →
          </button>
        </div>
      )}

      {trend != null && (
        <div className={`card readiness-banner ${trend >= PASS_TARGET ? 'good' : trend >= 65 ? 'close' : 'low'}`}>
          <Target size={20} />
          <div><strong>{trend >= PASS_TARGET ? 'On track to pass.' : trend >= 65 ? 'Close to passing range.' : 'Not exam-ready yet.'}</strong>{' '}
            Your recent mock average is {trend}%. {trend >= PASS_TARGET ? 'Keep taking a full-length each week to stay sharp.' : `Review the rationales from your misses and retake until you hold ${PASS_TARGET}%+.`}</div>
        </div>
      )}

      <div className="section-title">
        <div><p className="eyebrow">Full-length simulations</p><h2>Board-length exams</h2></div>
        <p className="muted">Built from {guideTotal} study-guide + {manualTotal} verified manual items, so a full-length rarely repeats what you have already seen.</p>
      </div>
      <div className="test-grid">
        {fullTests.map(t => {
          const a = attemptsFor(store, t.testId)
          const bestT = a.length ? Math.max(...a.map(pct)) : null
          return (
            <article key={t.testId} className={`test-card ${t.kind}`}>
              <div className="test-top">
                <Trophy size={20} />
                {bestT != null && <span className={`score-chip ${bestT >= PASS_TARGET ? 'good' : bestT >= 65 ? 'close' : 'low'}`}>Best {bestT}%</span>}
              </div>
              <h3>{t.title}</h3>
              <p>{t.blurb}</p>
              <div className="test-meta">
                <span><ClipboardList size={14} /> {t.count} questions</span>
                <span><Timer size={14} /> {t.minutes} min</span>
                {a.length > 0 && <span><RotateCcw size={14} /> {a.length} attempt{a.length > 1 ? 's' : ''}</span>}
              </div>
              <button className="btn" onClick={() => start(t)}>{a.length ? 'Retake test' : 'Start test'}</button>
            </article>
          )
        })}
      </div>

      {manualTests.length > 0 && (
        <>
          <div className="section-title" style={{ marginTop: 28 }}>
            <div><p className="eyebrow">Course manuals</p><h2>Slide MCQ mocks</h2></div>
            <p className="muted"><ShieldCheck size={13} style={{ verticalAlign: '-2px' }} /> Verified answer keys only — does not overlap the study-guide mocks.</p>
          </div>
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

      <div className="section-title"><div><p className="eyebrow">Targeted practice</p><h2>Chapter tests</h2></div><p className="muted">Every verified question in the chapter, timed at 72 seconds each.</p></div>
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
