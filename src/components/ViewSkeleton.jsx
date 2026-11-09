import React from 'react'

export default function ViewSkeleton({ label = 'Loading…' }) {
  return (
    <div className="view-skeleton" role="status" aria-live="polite">
      <p className="eyebrow">{label}</p>
      <div className="skeleton-bar wide" />
      <div className="skeleton-bar" />
      <div className="skeleton-bar short" />
      <div className="skeleton-grid">
        <div className="skeleton-card" />
        <div className="skeleton-card" />
        <div className="skeleton-card" />
      </div>
    </div>
  )
}
