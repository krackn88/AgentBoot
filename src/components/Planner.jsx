import React, { useMemo } from 'react'
import { todayKey } from '../lib/store'

export function buildPlan(guide, examDate) {
  const start = new Date(); start.setHours(0, 0, 0, 0)
  const end = new Date(examDate + 'T00:00:00')
  const days = Math.max(7, Math.round((end - start) / 86400000))
  const units = guide.chapters.map(c => ({ chapter: c, weight: Math.max(1, Math.round(c.wordCount / 900) + c.questions.length) }))
  const totalW = units.reduce((a, u) => a + u.weight, 0)
  const plan = []; let cursor = 0
  units.forEach(u => {
    const span = Math.max(1, Math.round(u.weight / totalW * (days - 4)))
    plan.push({ chapterId: u.chapter.id, title: `${u.chapter.number}. ${u.chapter.shortTitle}`, startDay: cursor, days: span, questions: u.chapter.questions.length })
    cursor += span
  })
  const out = []
  for (let d = 0; d < days; d++) {
    const date = new Date(start); date.setDate(date.getDate() + d)
    const item = plan.find(p => d >= p.startDay && d < p.startDay + p.days)
    let task
    if (d >= days - 2) task = 'Final review: High-Yield Quick Reference, missed-question deck, early night.'
    else if (d >= days - 4) task = 'Take a 50-question timed exam simulator run, then review every rationale.'
    else if (item) task = d === item.startDay ? `Read: ${item.title}` : `Continue ${item.title}${item.questions ? ` · do its ${item.questions} practice questions` : ''}`
    else task = 'Review flashcards and missed questions.'
    out.push({ key: todayKey(date), label: date.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }), task })
  }
  return out
}

export default function Planner({ guide, store, update }) {
  const plan = useMemo(() => store.examDate ? buildPlan(guide, store.examDate) : [], [guide, store.examDate])
  const doneCount = plan.filter(d => store.planDone[d.key]).length
  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      <h1>Study Planner</h1>
      <p className="muted">The manual's rule: finish the whole course, then study no longer than 3 months. Pick your exam date and get a day-by-day plan weighted by chapter size and question count — ending with timed exams and high-yield review.</p>
      <div className="card">
        <label className="label">My exam date</label>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <input type="date" value={store.examDate} onChange={e => update({ examDate: e.target.value, planDone: {} })} />
        </div>
        {plan.length > 0 && <><div className="bar" style={{ marginTop: 16 }}><i style={{ width: `${plan.length ? doneCount / plan.length * 100 : 0}%` }} /></div>
          <p className="small muted">{doneCount}/{plan.length} days done · {plan.length} days until your exam</p></>}
      </div>
      {plan.map(d => (
        <label key={d.key} className="card" style={{ display: 'flex', gap: 12, alignItems: 'flex-start', marginTop: 10, cursor: 'pointer', opacity: store.planDone[d.key] ? .55 : 1 }}>
          <input type="checkbox" checked={!!store.planDone[d.key]} onChange={e => update(s => ({ ...s, planDone: { ...s.planDone, [d.key]: e.target.checked }, studyDates: [...new Set([...s.studyDates, todayKey()])] }))} />
          <span><strong>{d.label}</strong><br /><span className="muted">{d.task}</span></span>
        </label>
      ))}
      {!plan.length && <div className="card" style={{ marginTop: 12 }}>Choose an exam date above to generate your personal plan.</div>}
    </div>
  )
}
