import React, { useMemo } from 'react'
import { todayKey } from '../lib/store'
import { PageHeader } from './AppShell.jsx'

/**
 * Day-by-day plan between today and the exam.
 *
 * Two constraints matter: the run has to fit the chapters (21 of them plus a
 * practice block), and it must not sprawl. A date eight months out previously
 * produced a 240-row checklist with the whole course crammed into the last few
 * weeks — nobody works through that. The study window is capped, and the days
 * before it are shown as a deliberate "start later" note.
 */
export const MAX_STUDY_DAYS = 84

export function buildPlan(guide, examDate, { maxDays = MAX_STUDY_DAYS } = {}) {
  const startOfToday = new Date()
  startOfToday.setHours(0, 0, 0, 0)
  const end = new Date(`${examDate}T00:00:00`)
  const daysToExam = Math.max(0, Math.round((end - startOfToday) / 86400000))

  if (!Number.isFinite(daysToExam) || daysToExam < 1) {
    return { days: [], daysToExam, startIn: 0, capped: false, past: daysToExam < 0 }
  }

  // Reserve the final two days for high-yield and rest, and cap the run so a
  // distant date doesn't produce a 200-row checklist. Never clamp *above* the
  // available window — that was what dropped chapters from short runways.
  const window = Math.min(daysToExam, maxDays)
  const reserved = Math.min(2, Math.max(0, window - 1))
  const studyDays = Math.max(1, window - reserved)
  const startIn = Math.max(0, daysToExam - window)

  const units = guide.chapters
    .filter(c => c.wordCount > 0)
    .map(c => ({
      chapter: c,
      weight: Math.max(1, Math.round(c.wordCount / 900) + Math.max(1, c.questions.length)),
    }))
  const totalW = units.reduce((a, u) => a + u.weight, 0)

  // Distribute chapter-days across the study window. The previous version gave
  // every chapter at least one day, so with a short runway the spans overflowed
  // and the tail of the course silently never appeared. Instead, scale by weight
  // and, when there are fewer days than chapters, group consecutive chapters so
  // all 21 are still covered.
  const plan = []
  if (studyDays >= units.length) {
    // One day per chapter minimum, then hand out the remaining days by weight.
    // Computing boundaries from cumulative weights alone let trailing chapters
    // round to a zero-length span, so the end of the course silently vanished
    // from any plan longer than a few weeks.
    const leftover = studyDays - units.length
    const spans = units.map(u => 1)
    let assigned = 0
    const shares = units.map(u => (u.weight / totalW) * leftover)
    shares.forEach((share, i) => {
      const whole = Math.floor(share)
      spans[i] += whole
      assigned += whole
    })
    // distribute any rounding remainder to the heaviest chapters
    let rest = leftover - assigned
    const order = units.map((u, i) => i).sort((a, b) => shares[b] - shares[a])
    for (let k = 0; rest > 0 && k < order.length; k++, rest--) spans[order[k]] += 1

    let cursor = 0
    units.forEach((u, i) => {
      plan.push({
        chapterId: u.chapter.id,
        title: `${u.chapter.number}. ${u.chapter.shortTitle}`,
        startDay: cursor,
        days: spans[i],
        questions: u.chapter.questions.length,
      })
      cursor += spans[i]
    })
  } else {
    // Fewer days than chapters: split the ordered chapter list into contiguous
    // blocks of roughly equal weight, so the plan still reads 1 → 21 in order and
    // nothing is left out.
    const perDay = totalW / studyDays
    let group = { units: [], weight: 0 }
    const groups = []
    units.forEach((u, i) => {
      group.units.push(u)
      group.weight += u.weight
      const left = units.length - i - 1
      const daysLeft = studyDays - groups.length - 1
      if (group.weight >= perDay * 0.85 || left === daysLeft) {
        groups.push(group)
        group = { units: [], weight: 0 }
      }
    })
    if (group.units.length) groups.push(group)

    groups.forEach((g, i) => {
      const first = g.units[0].chapter
      const last = g.units[g.units.length - 1].chapter
      plan.push({
        chapterId: first.id,
        chapterIds: g.units.map(u => u.chapter.id),
        title: g.units.length > 1
          ? `${first.number}–${last.number}. ${first.shortTitle} → ${last.shortTitle}`
          : `${first.number}. ${first.shortTitle}`,
        startDay: Math.min(i, studyDays - 1),
        days: 1,
        // a block that covers several chapters needs more than a read: say so
        block: g.units.length > 1,
        questions: g.units.reduce((a, u) => a + u.chapter.questions.length, 0),
      })
    })
  }

  const out = []
  const start = new Date(startOfToday)
  start.setDate(start.getDate() + startIn)

  for (let d = 0; d < window; d++) {
    const date = new Date(start)
    date.setDate(date.getDate() + d)
    const remaining = window - d
    const item = plan.find(p => d >= p.startDay && d < p.startDay + p.days)

    let task
    let kind = 'study'
    if (remaining <= reserved && reserved > 0) {
      task = 'Final review: high-yield quick reference, missed-question deck, early night.'
      kind = 'final'
    } else if (item) {
      const load = item.block
        ? `${item.title} — skim for criteria, tables, and drug regimens (${item.questions} practice Q)`
        : d === item.startDay
          ? `Read: ${item.title}`
          : `Continue ${item.title}${item.questions ? ` · ${item.questions} practice questions` : ''}`
      task = load
    } else {
      task = 'Flashcards and missed questions.'
      kind = 'review'
    }

    out.push({
      key: todayKey(date),
      label: date.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }),
      task,
      kind,
    })
  }

  // Did every chapter make it into the plan? Grouped days cover several chapters,
  // so expand the grouping rather than trusting the row count.
  const coveredIds = new Set(plan.flatMap(p => (p.chapterIds || [p.chapterId])))
  const skipped = units.filter(u => !coveredIds.has(u.chapter.id)).map(u => u.chapter.number)
  const coveredAll = skipped.length === 0

  return { days: out, daysToExam, startIn, capped: daysToExam > maxDays, past: false, coveredAll, skipped }
}

export default function Planner({ guide, store, update }) {
  const { days, daysToExam, startIn, capped, past } = useMemo(
    () => (store.examDate ? buildPlan(guide, store.examDate) : { days: [], daysToExam: 0, startIn: 0, capped: false, past: false }),
    [guide, store.examDate],
  )
  const doneCount = days.filter(d => store.planDone[d.key]).length

  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      <PageHeader
        eyebrow="Schedule"
        title="Study planner"
        subtitle="Set your exam date for a day-by-day plan weighted by chapter size. The final four days are reserved for a full-length mock and high-yield review."
      />

      <div className="card">
        <label className="label" htmlFor="exam-date">My exam date</label>
        <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            id="exam-date"
            type="date"
            value={store.examDate}
            onChange={e => update({ examDate: e.target.value, planDone: {} })}
          />
          {store.examDate && (
            <span className={`pill ${daysToExam <= 21 ? 'gold' : ''}`}>
              {past ? 'Date has passed' : `${daysToExam} day${daysToExam === 1 ? '' : 's'} to go`}
            </span>
          )}
        </div>

        {days.length > 0 && (
          <>
            <div className="bar" style={{ marginTop: 16 }}>
              <i style={{ width: `${(doneCount / days.length) * 100}%` }} />
            </div>
            <p className="small muted" style={{ margin: '6px 0 0' }}>
              {doneCount}/{days.length} days done
              {startIn > 0 && ` · plan begins in ${startIn} days`}
            </p>
          </>
        )}

        {capped && (
          <p className="small muted" style={{ margin: '12px 0 0', lineHeight: 1.5 }}>
            You have {daysToExam} days, which is longer than a focused run needs. The plan covers the last{' '}
            {MAX_STUDY_DAYS} days — spend the time before that finishing coursework and keeping chapters warm,
            then start here.
          </p>
        )}
        {days.length > 0 && daysToExam <= 7 && (
          <p className="small" style={{ margin: '12px 0 0', lineHeight: 1.5, color: 'var(--ink2)' }}>
            <strong>{daysToExam} day{daysToExam === 1 ? '' : 's'} is not enough for a full pass.</strong>{' '}
            This plan triages: skim the high-yield tables in each block, then spend your remaining time on
            full-length mocks and reviewing rationales. Consider moving your exam date if your program allows it.
          </p>
        )}
        {past && (
          <p className="small" style={{ margin: '12px 0 0', color: 'var(--red)' }}>
            That date has already passed. Set a new one.
          </p>
        )}
      </div>

      {days.map(d => (
        <label
          key={d.key}
          className={`card plan-day ${d.kind}`}
          style={{ display: 'flex', gap: 12, alignItems: 'flex-start', marginTop: 10, cursor: 'pointer', opacity: store.planDone[d.key] ? 0.55 : 1 }}
        >
          <input
            type="checkbox"
            checked={!!store.planDone[d.key]}
            onChange={e => update(s => ({
              ...s,
              planDone: { ...s.planDone, [d.key]: e.target.checked },
              studyDates: [...new Set([...s.studyDates, todayKey()])],
            }))}
          />
          <span>
            <strong>{d.label}</strong>
            <br />
            <span className="muted">{d.task}</span>
          </span>
        </label>
      ))}

      {!days.length && !store.examDate && (
        <div className="card" style={{ marginTop: 12 }}>
          Choose an exam date above to generate your personal plan.
        </div>
      )}
    </div>
  )
}
