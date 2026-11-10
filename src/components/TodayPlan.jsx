import React, { useMemo } from 'react'
import { ArrowRight, Clock, Flame, Target, Sparkles } from 'lucide-react'
import { splitDue, deckStats, dateKey } from '../lib/srs'

/**
 * One screen, one decision: what should I do in the next 30 minutes?
 * Prioritises overdue reviews → weakest chapter → next unread chapter.
 */
export default function TodayPlan({ cards, srs, weakestChapter, nextChapter, streak, examDate, onGo, onOpenChapter, onQuiz }) {
  const { reviews, fresh } = useMemo(() => splitDue(cards || [], srs || {}), [cards, srs])
  const stats = useMemo(() => deckStats(cards || [], srs || {}), [cards, srs])

  const daysToExam = examDate
    ? Math.ceil((new Date(examDate + 'T12:00:00') - new Date()) / 86400000)
    : null

  const blocks = []

  if (reviews.length) {
    blocks.push({
      key: 'review',
      icon: Clock,
      title: `Clear ${reviews.length} overdue card${reviews.length === 1 ? '' : 's'}`,
      detail: 'Reviews decay if skipped — this is the cheapest ground you can hold today.',
      cta: 'Start review',
      go: () => onGo('flashcards'),
      tone: 'hot',
    })
  }

  if (weakestChapter && weakestChapter.pct < 75) {
    blocks.push({
      key: 'weak',
      icon: Target,
      title: `Review ${weakestChapter.shortTitle || weakestChapter.title}`,
      detail: `${weakestChapter.number}. ${weakestChapter.shortTitle || weakestChapter.title} is your lowest-scoring chapter at ${weakestChapter.pct}%.`,
      cta: 'Quiz it now',
      go: () => onQuiz(weakestChapter.id),
    })
  }

  if (nextChapter) {
    blocks.push({
      key: 'next',
      icon: nextChapter ? ArrowRight : Sparkles,
      title: `Read ${nextChapter.number}. ${nextChapter.shortTitle}`,
      detail: 'Next unopened chapter — the fastest way to move coverage.',
      cta: 'Open chapter',
      go: () => onOpenChapter(nextChapter.id),
    })
  }

  // A brand-new account has no reviews and no history: offer a first session,
  // not an empty checklist.
  if (!blocks.length) {
    return (
      <div className="card today-plan">
        <p className="label" style={{ margin: 0 }}>Start here</p>
        <h3 style={{ margin: '6px 0 8px' }}>Nothing scheduled yet — here is the first move.</h3>
        <p className="muted" style={{ marginBottom: 12, lineHeight: 1.6 }}>
          {stats.fresh > 0
            ? `${stats.fresh} cards are waiting. New cards are introduced a handful at a time so the deck stays manageable.`
            : 'Open a chapter to begin, then answer its questions — that is what feeds your readiness score.'}
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" className="btn gold" onClick={() => onGo('flashcards')}>Start 10 cards →</button>
          <button type="button" className="btn" onClick={() => onGo('library')}>Open the study guide</button>
        </div>
      </div>
    )
  }

  return (
    <div className="card today-plan">
      <div className="today-plan-head">
        <div>
          <p className="label" style={{ margin: 0 }}>Today</p>
          <h3 style={{ margin: '6px 0 0' }}>Do these, in this order</h3>
        </div>
        <div className="today-plan-meta">
          {streak > 0 && <span className="pill"><Flame size={13} style={{ verticalAlign: '-2px' }} /> {streak}-day streak</span>}
          {daysToExam != null && (
            <span className={`pill ${daysToExam <= 21 ? 'gold' : ''}`}>
              {daysToExam > 0 ? `${daysToExam} days to exam` : 'Exam date passed'}
            </span>
          )}
        </div>
      </div>
      <ol className="today-list">
        {blocks.slice(0, 3).map((b, idx) => {
          const Icon = b.icon
          return (
            <li key={b.key} className={`today-item ${b.tone || ''}`}>
              <span className="today-num">{idx + 1}</span>
              <div className="today-body">
                <strong><Icon size={15} style={{ verticalAlign: '-2px', marginRight: 6 }} />{b.title}</strong>
                <p className="small muted" style={{ margin: '4px 0 8px', lineHeight: 1.5 }}>{b.detail}</p>
                <button type="button" className={idx === 0 ? 'btn gold' : 'btn ghost'} onClick={b.go}>{b.cta} →</button>
              </div>
            </li>
          )
        })}
      </ol>
      {stats.dueNow === 0 && stats.learned > 0 && (
        <p className="small muted" style={{ margin: '4px 0 0' }}>
          Reviews all clear for today — {stats.mature} cards are holding at a 21-day interval.
        </p>
      )}
    </div>
  )
}
