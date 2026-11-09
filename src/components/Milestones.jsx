import React, { useEffect, useMemo, useState } from 'react'
import { MILESTONE_DEFS, buildMilestoneContext, earnedMilestones, popNewMilestoneToasts } from '../lib/milestones'

export default function Milestones({ store, stats, weeksComplete }) {
  const ctx = useMemo(() => buildMilestoneContext(store, stats, weeksComplete), [store, stats, weeksComplete])
  const earned = useMemo(() => earnedMilestones(ctx), [ctx])
  const [toast, setToast] = useState(null)

  useEffect(() => {
    const fresh = popNewMilestoneToasts(ctx)
    if (fresh.length) setToast(fresh[fresh.length - 1])
  }, [ctx])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 5000)
    return () => clearTimeout(t)
  }, [toast])

  return (
    <>
      {toast && (
        <div className="milestone-toast no-print" role="status">
          <span className="milestone-toast-emoji">{toast.emoji}</span>
          <div>
            <strong>Milestone: {toast.label}</strong>
            <p className="small" style={{ margin: '2px 0 0' }}>{toast.desc}</p>
          </div>
          <button type="button" className="milestone-toast-close" onClick={() => setToast(null)} aria-label="Close">×</button>
        </div>
      )}
      <div className="card milestone-panel no-print">
        <p className="label">Study milestones</p>
        <h3 style={{ margin: '4px 0 10px' }}>Badges you earn as you go</h3>
        <div className="milestone-grid">
          {MILESTONE_DEFS.map(m => {
            const on = earned.some(e => e.id === m.id)
            return (
              <div key={m.id} className={`milestone-badge ${on ? 'earned' : ''}`} title={m.desc}>
                <span className="milestone-emoji" aria-hidden>{m.emoji}</span>
                <span className="milestone-label">{m.label}</span>
              </div>
            )
          })}
        </div>
      </div>
    </>
  )
}
