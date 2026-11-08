import React from 'react'
import { House, Library, BookOpen, NotebookPen, Trophy, ClipboardCheck, Layers3, Zap, CalendarDays, Info } from 'lucide-react'
import { BETA_OPEN, PLATFORM } from '../lib/config'

const GROUPS = [
  { label: 'Overview', items: [['dashboard', House, 'Dashboard']] },
  { label: 'Learn', items: [['library', Library, 'Study guide'], ['manuals', BookOpen, 'Full manuals'], ['quickref', Zap, 'High-yield']] },
  { label: 'Practice', items: [['workbooks', NotebookPen, 'Workbooks'], ['tests', Trophy, 'Mock exams'], ['quiz', ClipboardCheck, 'Question bank'], ['flashcards', Layers3, 'Flashcards']] },
  { label: 'Plan', items: [['planner', CalendarDays, 'Study planner']] },
]

export function Sidebar({ view, go, readiness, doneCh, totalCh, answered, totalQ, streak }) {
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
        <p className="tagline">Structured study, clinical workbooks, and board-style testing — built from the full APEA 2026 course.</p>
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
        <p>{doneCh}/{totalCh} chapters · {answered}/{totalQ} questions</p>
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

export function MobileNav({ view, go }) {
  const tabs = [
    ['dashboard', House, 'Home'],
    ['library', Library, 'Guide'],
    ['workbooks', NotebookPen, 'Books'],
    ['tests', Trophy, 'Exams'],
    ['quiz', ClipboardCheck, 'Quiz'],
  ]
  const active = (k) => view === k || (view === 'reader' && k === 'library')
  return (
    <nav className="bottomnav" aria-label="Primary">
      {tabs.map(([k, Icon, label]) => (
        <button key={k} type="button" className={active(k) ? 'active' : ''} onClick={() => go(k)}>
          <Icon size={20} strokeWidth={2} />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  )
}
