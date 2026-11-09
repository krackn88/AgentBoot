import React, { useMemo, useState, useEffect } from 'react'
import { shuffle, bumpDaily } from '../lib/store'
import { PageHeader } from './AppShell.jsx'

export function buildDecks(guide, store, pearlCards = [], questionPool = null) {
  const high = []
  const walk = (node) => (node?.sections || []).forEach(s => s.blocks.forEach(b => {
    if (b.type === 'table') b.rows.forEach(r => { if (r[0] && r[1]) high.push({ id: 'hy-' + high.length, front: r[0], back: r.slice(1).join(' — '), tag: s.title }) })
  }))
  walk(guide.quickRef)
  const labs = []
  const ch1 = guide.chapters[0]
  ch1?.sections.filter(s => /labs/i.test(s.title)).forEach(s => s.blocks.forEach(b => {
    if (b.type === 'table') b.rows.forEach(r => { if (r[0] && r[1]) labs.push({ id: 'lab-' + labs.length, front: r[0], back: r.slice(1).join(' — '), tag: 'Labs to memorize' }) })
  }))
  const pool = questionPool || guide.chapters.flatMap(c => c.questions.map(q => ({ ...q, chapterTitle: c.shortTitle })))
  const qs = pool.filter(q => q.correctIndex != null && q.options?.[q.correctIndex])
    .map(q => ({ id: 'q-' + q.id, front: q.stem, back: `${q.options[q.correctIndex]} — ${q.explanation || ''}`, tag: q.chapterTitle || q.chapterId }))
  const missed = qs.filter(c => store.answers[c.id.slice(2)] && !store.answers[c.id.slice(2)].correct)
  const pearls = pearlCards.map(c => ({ id: c.id, front: c.front, back: c.back, tag: c.tag }))
  return { highyield: { label: `High-Yield Quick Reference (${high.length})`, cards: high }, labs: { label: `Labs to Commit to Memory (${labs.length})`, cards: labs }, questions: { label: `Question Cards (${qs.length})`, cards: qs }, pearls: { label: `Clinical pearls (${pearls.length})`, cards: pearls },
    missed: { label: `My Missed Questions (${missed.length})`, cards: missed } }
}

export default function Flashcards({ guide, store, update, pearlCards = [], questionPool }) {
  const decks = useMemo(() => buildDecks(guide, store, pearlCards, questionPool), [guide, store, pearlCards, questionPool])
  const [deckId, setDeckId] = useState('highyield')
  const [order, setOrder] = useState(null); const [i, setI] = useState(0); const [flip, setFlip] = useState(false)
  const deck = decks[deckId]
  const cards = order && order.deck === deckId ? order.cards : deck.cards
  const card = cards[i % Math.max(1, cards.length)]
  const mastered = deck.cards.filter(c => (store.cardBox[c.id] || 0) >= 3).length
  useEffect(() => {
    function onKey(e) {
      if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); setFlip(f => !f) }
      if (e.key === '1') rate(false); if (e.key === '2') rate(true)
      if (e.key === 'ArrowRight') { setFlip(false); setI(v => v + 1) }
    }
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey)
  })
  function rate(known) {
    if (!card) return
    update(s => bumpDaily({ ...s, cardBox: { ...s.cardBox, [card.id]: Math.max(0, Math.min(3, (s.cardBox[card.id] || 0) + (known ? 1 : -1))) } }, 'cards', 1))
    setFlip(false); setI(v => v + 1)
  }
  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      <PageHeader eyebrow="Active recall" title="Flashcards" subtitle="High-yield tables, labs, clinical pearls, and graded question cards. Space to flip; rate cards until mastered (3× correct). Keyboard: 1 = still learning, 2 = I know this." />
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '16px 0' }}>
        {Object.entries(decks).map(([k, d]) => <button key={k} className={k === deckId ? 'btn' : 'btn ghost'} onClick={() => { setDeckId(k); setI(0); setFlip(false); setOrder(null) }}>{d.label}</button>)}
      </div>
      <div className="bar"><i style={{ width: `${deck.cards.length ? mastered / deck.cards.length * 100 : 0}%` }} /></div>
      <p className="small muted">{mastered}/{deck.cards.length} mastered in this deck · Card {cards.length ? (i % cards.length) + 1 : 0} of {cards.length}</p>
      {card ? <>
        <div className={`flashcard ${flip ? 'flipped' : ''}`} onClick={() => setFlip(!flip)}>
          <div className="fc-inner">
            <div className="fc-face"><p className="label">{card.tag} · tap to flip</p><p style={{ fontSize: 21, lineHeight: 1.5 }}><strong>{card.front}</strong></p></div>
            <div className="fc-face fc-back"><p className="label" style={{ color: '#9db8d8' }}>{card.tag}</p><p style={{ fontSize: 18, lineHeight: 1.6 }}>{card.back}</p></div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          <button className="btn ghost" onClick={() => rate(false)}>Still learning</button>
          <button className="btn" onClick={() => rate(true)}>✓ I know this</button>
          <button className="btn ghost" onClick={() => { setOrder({ deck: deckId, cards: shuffle(deck.cards) }); setI(0); setFlip(false) }}>Shuffle deck</button>
          <button className="btn ghost" onClick={() => { setFlip(false); setI(v => v + 1) }}>Skip →</button>
        </div>
      </> : <div className="card">No cards here yet. {deckId === 'missed' ? 'Miss a practice question and it will show up here automatically.' : 'This deck is empty in the source guide.'}</div>}
    </div>
  )
}
