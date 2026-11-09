import React, { useMemo } from 'react'
import { buildTwelveWeekPath } from '../lib/studyPath'
import { ChevronRight } from 'lucide-react'

export default function StudyPath({ guide, store, update, onOpenChapter, onGo }) {
  const weeks = useMemo(() => buildTwelveWeekPath(guide), [guide])
  const done = store.studyPathDone || {}
  const activeWeek = weeks.find(w => !w.tasks.every(t => done[`${w.week}-${t.key}`]))?.week ?? 12

  function toggle(week, key) {
    const id = `${week}-${key}`
    update(s => ({
      ...s,
      studyPathDone: { ...(s.studyPathDone || {}), [id]: !done[id] },
      studyDates: [...new Set([...s.studyDates, new Date().toISOString().slice(0, 10)])],
    }))
  }

  return (
    <div className="study-path card no-print">
      <div className="study-path-head">
        <div>
          <p className="label">Guided path</p>
          <h3 style={{ margin: '4px 0 6px' }}>12-week board prep arc</h3>
          <p className="muted small" style={{ margin: 0, lineHeight: 1.5 }}>Follow every chapter once, layer workbooks and quizzes, then finish with mocks and high-yield. Set an exam date in the Planner for a daily countdown plan.</p>
        </div>
        <button type="button" className="btn ghost" onClick={() => onGo('planner')}>Custom exam date →</button>
      </div>
      <div className="study-path-weeks">
        {weeks.map(w => {
          const complete = w.tasks.every(t => done[`${w.week}-${t.key}`])
          const isActive = w.week === activeWeek
          return (
            <details key={w.week} className={`study-week ${isActive ? 'active' : ''} ${complete ? 'done' : ''}`} open={isActive}>
              <summary>
                <span className="week-num">Week {w.week}</span>
                <span className="week-meta">Ch. {w.chapterIds.length ? guide.chapters.find(c => c.id === w.chapterIds[0])?.number : ''}–{w.chapterIds.length ? guide.chapters.find(c => c.id === w.chapterIds[w.chapterIds.length - 1])?.number : ''}</span>
                {complete && <span className="pill" style={{ marginLeft: 'auto' }}>Done</span>}
              </summary>
              <ul className="study-week-tasks">
                {w.tasks.map(t => {
                  const id = `${w.week}-${t.key}`
                  return (
                    <li key={t.key}>
                      <label>
                        <input type="checkbox" checked={!!done[id]} onChange={() => toggle(w.week, t.key)} />
                        <strong>{t.label}</strong> — {t.detail}
                      </label>
                      {t.key.endsWith('-read') && w.chapterIds[0] && (
                        <button type="button" className="linkbtn" onClick={() => onOpenChapter(w.chapterIds[0])}>Open chapter <ChevronRight size={14} /></button>
                      )}
                      {t.key.endsWith('-mock') && (
                        <button type="button" className="linkbtn" onClick={() => onGo('tests')}>Go to mocks <ChevronRight size={14} /></button>
                      )}
                      {t.key.endsWith('-hy') && (
                        <button type="button" className="linkbtn" onClick={() => onGo('quickref')}>High-yield →</button>
                      )}
                    </li>
                  )
                })}
              </ul>
            </details>
          )
        })}
      </div>
    </div>
  )
}
