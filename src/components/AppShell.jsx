import React, { useEffect, useState } from 'react'
import { House, Library, BookOpen, NotebookPen, Trophy, ClipboardCheck, Layers3, Zap, CalendarDays, Info, MoreHorizontal } from 'lucide-react'
import { BETA_OPEN, PLATFORM } from '../lib/config'

const GROUPS = [
  { label: 'Overview', items: [['dashboard', House, 'Dashboard']] },
  { label: 'Learn', items: [['library', Library, 'Study guide'], ['manuals', BookOpen, 'Full manuals'], ['quickref', Zap, 'High-yield']] },
  { label: 'Practice', items: [['workbooks', NotebookPen, 'Workbooks'], ['tests', Trophy, 'Mock exams'], ['quiz', ClipboardCheck, 'Question bank'], ['flashcards', Layers3, 'Flashcards']] },
  { label: 'Plan', items: [['planner', CalendarDays, 'Study planner']] },
]

export function Sidebar({ view, go, readiness, doneCh, totalCh, answered, totalQ, guideQ, manualQ, streak }) {
  const active = (k) => view === k || (view === 'reader' && k === 'library')
  return (
    <aside className="sidebar pro">
      {BETA_OPEN && (
        <div className="beta-ribbon">
          <span className="beta-dot" aria-hidden /> {PLATFORM.betaLabel}
        </div>
      )}
      <div className="brand-block">
        <p className="brand-kicker">APEA 2026 · FNP / AGPCNP</p>
        <div className="logo">FNP Board Prep</div>
        <p className="tagline">Chapters, mocks, and tracking — from official APEA 2026 course manuals.</p>
      </div>
      <nav className="side-nav" aria-label="Main">
        {GROUPS.map(g => (
          <div key={g.label} className="nav-group">
            <p className="nav-group-label">{g.label}</p>
            {g.items.map(([k, Icon, label]) => (
              <button key={k} type="button" className={`navbtn ${active(k) ? 'active' : ''}`} onClick={() => go(k)}>
                <Icon size={17} strokeWidth={2} />{label}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <div className="sidefoot">
        <p className="sidefoot-label">Exam readiness</p>
        <strong>{readiness}%</strong>
        <div className="bar side-bar"><i style={{ width: `${readiness}%` }} /></div>
        <p>{doneCh}/{totalCh} chapters · {answered}/{totalQ} Q tried</p>
        {(guideQ > 0 || manualQ > 0) && <p className="sidefoot-detail">{guideQ} guide + {manualQ || 0} manual keyed</p>}
        <p>{streak}-day streak</p>
      </div>
      <button type="button" className="navbtn subtle" onClick={() => go('about')}><Info size={16} /> About & access</button>
    </aside>
  )
}

export function PageHeader({ eyebrow, title, subtitle, actions }) {
  return (
    <header className="page-header">
      <div className="page-header-text">
        {eyebrow && <p className="eyebrow page-eyebrow">{eyebrow}</p>}
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  )
}

const MORE_LINKS = [
  ['workbooks', NotebookPen, 'Workbooks'],
  ['manuals', BookOpen, 'Manuals'],
  ['flashcards', Layers3, 'Cards'],
  ['planner', CalendarDays, 'Planner'],
  ['quickref', Zap, 'High-yield'],
  ['about', Info, 'About'],
]

export function MobileNav({ view, go }) {
  const [moreOpen, setMoreOpen] = useState(false)
  const tabs = [
    ['dashboard', House, 'Home'],
    ['library', Library, 'Guide'],
    ['tests', Trophy, 'Mocks'],
    ['quiz', ClipboardCheck, 'Quiz'],
    ['more', MoreHorizontal, 'More'],
  ]
  const active = (k) => {
    if (k === 'more') return moreOpen || MORE_LINKS.some(([id]) => view === id)
    return view === k || (view === 'reader' && k === 'library')
  }
  useEffect(() => {
    if (!moreOpen) return
    const close = () => setMoreOpen(false)
    window.addEventListener('hashchange', close)
    return () => window.removeEventListener('hashchange', close)
  }, [moreOpen])

  return (
    <>
      {moreOpen && (
        <div className="mobile-more-sheet no-print" role="dialog" aria-label="More study tools">
          <p className="label" style={{ margin: '0 0 8px' }}>More — one tap</p>
          <div className="mobile-more-grid">
            {MORE_LINKS.map(([k, Icon, label]) => (
              <button key={k} type="button" className="btn ghost" onClick={() => { go(k); setMoreOpen(false) }}>
                <Icon size={18} /> {label}
              </button>
            ))}
          </div>
          <button type="button" className="btn ghost mobile-more-close" onClick={() => setMoreOpen(false)}>Close</button>
        </div>
      )}
      <nav className="bottomnav" aria-label="Primary">
        {tabs.map(([k, Icon, label]) => (
          <button
            key={k}
            type="button"
            className={active(k) ? 'active' : ''}
            aria-expanded={k === 'more' ? moreOpen : undefined}
            onClick={() => (k === 'more' ? setMoreOpen(o => !o) : (go(k), setMoreOpen(false)))}
          >
            <Icon size={20} strokeWidth={2} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </>
  )
}
