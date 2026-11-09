import React from 'react'
import { ArrowRight, TrendingUp } from 'lucide-react'

/**
 * The readiness number with its math exposed. A clinician should be able to
 * disagree with the weighting and see exactly which part is dragging the score.
 */
export default function ReadinessPanel({ model, onGo }) {
  const { score, parts, weakest } = model

  return (
    <section className="card readiness-panel" aria-label="Readiness breakdown">
      <div className="rp-head">
        <div>
          <p className="label" style={{ margin: 0 }}>Board readiness — the math</p>
          <h2 className="rp-score">{score}<span>%</span></h2>
          <p className="small muted" style={{ margin: 0 }}>
            Study tracker, not a score prediction. Weights: 40% coverage · 35% practice · 25% retention.
          </p>
        </div>
        <div className="rp-next">
          <p className="label" style={{ margin: 0 }}>Biggest lever right now</p>
          <p className="rp-next-label">{weakest.label}</p>
          <button type="button" className="btn gold" onClick={() => onGo(weakest.go)}>
            {weakest.action} <ArrowRight size={15} style={{ verticalAlign: '-2px' }} />
          </button>
        </div>
      </div>

      <div className="rp-parts">
        {parts.map(p => {
          const pct = Math.round(p.value * 100)
          const earned = Math.round(p.value * p.weight * 100)
          return (
            <div key={p.id} className="rp-part">
              <div className="rp-part-head">
                <strong>{p.label}</strong>
                <span className="rp-part-earned">{earned}<span className="muted">/{Math.round(p.weight * 100)} pts</span></span>
              </div>
              <div className="bar">
                <i
                  style={{
                    width: `${pct}%`,
                    background: pct >= 75 ? 'var(--green)' : pct >= 40 ? 'var(--gold)' : 'var(--red)',
                  }}
                />
              </div>
              <p className="small muted rp-part-detail">{p.detail}</p>
            </div>
          )
        })}
      </div>

      <p className="rp-foot small muted">
        <TrendingUp size={14} style={{ verticalAlign: '-2px' }} /> Accuracy below 50% earns almost no practice credit;
        75%+ earns full credit. Retention counts cards that reached a 21-day interval.
      </p>
    </section>
  )
}
