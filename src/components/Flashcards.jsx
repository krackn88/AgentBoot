import React, { useEffect, useMemo, useState } from 'react'
import { shuffle, bumpDaily } from '../lib/store'
import { PageHeader } from './AppShell.jsx'
import { GRADES, deckStats, dueCards, splitDue, forecast, isDue, isNew, schedule } from '../lib/srs'
import { isUniqueGraded } from '../lib/quality'
import { drillsFromTable, tableIsDrillable, topicPhrase, splitTopic, answerWithWhy, clozeFrom, pearlPrompt } from '../lib/drills'

const MASTERED_INTERVAL = 21

export function buildDecks(guide, store, pearlCards = [], questionPool = null) {
  // Table cards use the same question generator as the workbook, so a card front is
  // a real question ("In hives, what is the itch like?") rather than a bare cell
  // ("Live vaccines") that tells the student nothing about what is being asked.
  const drillCards = (table, node, prefix, tag) => {
    if (!tableIsDrillable(table)) return []
    return drillsFromTable(table, { section: tag, tableKey: prefix }).map(d => ({
      id: `${prefix}-${d.id}`,
      front: d.prompt,
      back: d.answer,
      tag,
    }))
  }

  const high = []
  ;(guide.quickRef?.sections || []).forEach(s => (s.blocks || []).forEach((b, bi) => {
    if (b.type === 'table') high.push(...drillCards(b, s, `hy${bi}`, s.title))
  }))
  const labs = []
  const ch1 = guide.chapters[0]
  ;(ch1?.sections || []).filter(s => /labs/i.test(s.title)).forEach(s => (s.blocks || []).forEach((b, bi) => {
    if (b.type === 'table') labs.push(...drillCards(b, s, `lab${bi}`, 'Labs to commit to memory'))
  }))

  const pool = questionPool || guide.chapters.flatMap(c => c.questions.map(q => ({ ...q, chapterTitle: c.shortTitle })))
  const qs = pool.filter(isUniqueGraded)
    .map(q => ({
      id: 'q-' + q.id,
      front: q.stem,
      back: answerWithWhy(q.options[q.correctIndex], q.explanation),
      tag: q.chapterTitle || q.chapterId,
      anchor: q.anchor,
    }))
  const missed = qs.filter(c => store.answers[c.id.slice(2)] && !store.answers[c.id.slice(2)].correct)
  // High-yield cards already cover the must-know rule table. A pearl whose text is
  // the same rule would ask the identical question in a second deck, so only
  // pearls that add something (tips, rationales) become pearl cards.
  const covered = new Set(high.map(c => (c.back || '').toLowerCase().replace(/[^a-z0-9]+/g, '')))
  const pearls = pearlCards.flatMap(c => {
    const { topic, detail } = splitTopic(c.front)
    if (topic) {
      if (covered.has((detail || '').toLowerCase().replace(/[^a-z0-9]+/g, ''))) return []
      return [{ id: c.id, front: pearlPrompt(topic), back: detail, tag: c.tag || 'Clinical pearl' }]
    }
    const cloze = clozeFrom(c.front)
    if (!cloze) return []
    return [{ id: c.id, front: cloze.prompt, back: `${cloze.answer} — ${cloze.full}`, tag: c.tag || 'Clinical pearl' }]
  })

  return {
    due: { label: 'Due today', cards: [] },
    highyield: { label: `High-yield tables (${high.length})`, cards: high },
    labs: { label: `Labs to commit (${labs.length})`, cards: labs },
    questions: { label: `Question cards (${qs.length})`, cards: qs },
    pearls: { label: `Clinical pearls (${pearls.length})`, cards: pearls },
    missed: { label: `My missed questions (${missed.length})`, cards: missed },
  }
}

/** Every card across every deck, deduped by id — the source for the global due queue. */
export function allCards(decks) {
  const seen = new Set()
  const out = []
  Object.entries(decks).forEach(([deckId, d]) => {
    if (deckId === 'due') return
    d.cards.forEach(c => {
      if (seen.has(c.id)) return
      seen.add(c.id)
      out.push({ ...c, deckId, deckLabel: d.label })
    })
  })
  return out
}

function ForecastBar({ buckets }) {
  const max = Math.max(1, ...buckets)
  return (
    <div className="fc-forecast" aria-label="Reviews due over the next 14 days">
      {buckets.map((n, i) => (
        <div key={i} className="fc-forecast-col" title={`${i === 0 ? 'Today' : `In ${i} day${i === 1 ? '' : 's'}`}: ${n} card${n === 1 ? '' : 's'}`}>
          <i style={{ height: `${Math.round((n / max) * 100)}%` }} className={i === 0 && n ? 'hot' : ''} />
        </div>
      ))}
    </div>
  )
}

export default function Flashcards({ guide, store, update, pearlCards = [], questionPool }) {
  const decks = useMemo(() => buildDecks(guide, store, pearlCards, questionPool), [guide, store, pearlCards, questionPool])
  const srs = store.srs || {}
  const [deckId, setDeckId] = useState('due')
  const [queue, setQueue] = useState(null)
  const [i, setI] = useState(0)
  const [flip, setFlip] = useState(false)
  const [lastGrade, setLastGrade] = useState(null)

  const pool = useMemo(() => allCards(decks), [decks])
  const { reviews, fresh } = useMemo(() => splitDue(pool, srs), [pool, srs])
  const dueAll = useMemo(() => dueCards(pool, srs, 60), [pool, srs])
  const stats = useMemo(() => deckStats(pool, srs), [pool, srs])
  const days = useMemo(() => forecast(pool, srs, 14), [pool, srs])

  const deckCards = deckId === 'due' ? dueAll : decks[deckId]?.cards || []
  const cards = queue && queue.deck === deckId ? queue.cards : deckCards
  const card = cards[i]

  useEffect(() => { setFlip(false); setLastGrade(null) }, [deckId, i])

  function grade(g) {
    if (!card) return
    const next = schedule(srs[card.id], g)
    update(s => bumpDaily({ ...s, srs: { ...(s.srs || {}), [card.id]: next } }, 'cards', 1))
    setLastGrade({ grade: g, next })
    setFlip(false)
    // 'again' puts the card back at the end of this session too
    if (g === 'again') setQueue(q => ({ deck: deckId, cards: [...(q?.deck === deckId ? q.cards : deckCards), card] }))
    setI(v => v + 1)
  }

  useEffect(() => {
    function onKey(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); if (!flip) setFlip(true); else grade('good') }
      if (flip) {
        if (e.key === '1') grade('again')
        if (e.key === '2') grade('hard')
        if (e.key === '3') grade('good')
      }
      if (e.key === 'ArrowRight') { setFlip(false); setI(v => v + 1) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [flip, card, srs, deckId])

  const deckStat = deckStats(deckCards, srs)
  const doneThisSession = Math.min(i, cards.length)

  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      <PageHeader
        eyebrow="Spaced repetition"
        title="Flashcards"
        subtitle="Cards come back exactly when you're about to forget them. Grade honestly — Again resets, Good grows the interval. Space flips · 1/2/3 grades."
      />

      <div className="fc-topbar">
        <div className="fc-topbar-stat">
          <p className="label">Reviews due</p>
          <p className="fc-big">{reviews.length || '—'}</p>
          <p className="small muted">{reviews.length ? 'overdue' : 'all clear'}</p>
        </div>
        <div className="fc-topbar-stat">
          <p className="label">Learning</p>
          <p className="fc-big">{stats.learned}</p>
          <p className="small muted">{stats.mature} mastered (21d+)</p>
        </div>
        <div className="fc-topbar-stat">
          <p className="label">Not started</p>
          <p className="fc-big">{stats.fresh}</p>
        </div>
        <div className="fc-topbar-chart">
          <p className="label" style={{ marginBottom: 6 }}>Next 14 days</p>
          <ForecastBar buckets={days} />
        </div>
      </div>

      <div className="fc-deck-row">
        <button className={deckId === 'due' ? 'btn' : 'btn ghost'} onClick={() => { setDeckId('due'); setQueue(null); setI(0) }}>
          Study now ({dueAll.length})
        </button>
        {Object.entries(decks).filter(([k]) => k !== 'due').map(([k, d]) => (
          <button key={k} className={k === deckId ? 'btn' : 'btn ghost'} onClick={() => { setDeckId(k); setQueue(null); setI(0) }}>
            {d.label}
          </button>
        ))}
      </div>

      {deckId !== 'due' && deckCards.length > 0 && (
        <div className="fc-deckbar">
          <div className="bar"><i style={{ width: `${deckStat.total ? (deckStat.mature / deckStat.total) * 100 : 0}%` }} /></div>
          <p className="small muted">
            {deckStat.mature}/{deckStat.total} mastered · {deckStat.dueNow} due now · {deckStat.fresh} new
          </p>
          <button className="btn ghost fc-shuffle" onClick={() => { setQueue({ deck: deckId, cards: shuffle(deckCards) }); setI(0) }}>Shuffle</button>
        </div>
      )}

      {card ? (
        <>
          <div className="fc-progress">
            <span className="small muted">{Math.min(i + 1, cards.length)} / {cards.length}</span>
            {lastGrade && (
              <span className="small muted">
                Last: {lastGrade.grade} → {lastGrade.next.interval === 0 ? 'today' : `in ${lastGrade.next.interval}d`}
              </span>
            )}
          </div>
          <button type="button" className={`flashcard ${flip ? 'flipped' : ''}`} onClick={() => setFlip(f => !f)} aria-label="Flip card">
            <div className="fc-inner">
              <div className="fc-face">
                <p className="label">{card.tag} · {isNew(srs[card.id]) ? 'new' : isDue(srs[card.id]) ? 'due' : 'ahead of schedule'}</p>
                <p className="fc-front-text">{card.front}</p>
                <p className="fc-hint small muted">Tap or press space to reveal</p>
              </div>
              <div className="fc-face fc-back">
                <p className="label" style={{ color: '#9db8d8' }}>{card.tag}</p>
                <p className="fc-back-text">{card.back}</p>
                {card.anchor?.section && (
                  <p className="fc-anchor small">
                    Verify in manual {card.anchor.manualId} — “{card.anchor.section}”
                  </p>
                )}
              </div>
            </div>
          </button>

          {flip ? (
            <div className="fc-grades">
              {GRADES.map(g => (
                <button key={g.id} type="button" className={`btn fc-grade ${g.id}`} onClick={() => grade(g.id)}>
                  <strong>{g.label}</strong>
                  <span className="small">{g.hint} · {g.key}</span>
                </button>
              ))}
            </div>
          ) : (
            <div className="fc-grades">
              <button type="button" className="btn" onClick={() => setFlip(true)}>Show answer (space)</button>
              <button type="button" className="btn ghost" onClick={() => { setFlip(false); setI(v => v + 1) }}>Skip →</button>
            </div>
          )}
        </>
      ) : (
        <div className="card fc-empty">
          {deckId === 'due' ? (
            <>
              <h3 style={{ marginTop: 0 }}>Nothing due right now.</h3>
              <p className="muted" style={{ lineHeight: 1.6 }}>
                That's the system working. Come back tomorrow, or pull a deck forward to study ahead.
              </p>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
                <button className="btn" onClick={() => { setDeckId('highyield'); setQueue(null); setI(0) }}>Study high-yield →</button>
                <button className="btn ghost" onClick={() => { setDeckId('pearls'); setQueue(null); setI(0) }}>Clinical pearls</button>
              </div>
            </>
          ) : (
            <p className="muted">
              {deckId === 'missed'
                ? 'Miss a practice question and it lands here automatically.'
                : 'This deck is empty in the source guide.'}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
