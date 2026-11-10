import React, { useState } from 'react'
import { FileText, Search, ExternalLink, ChevronDown } from 'lucide-react'

/**
 * Lets a student check an answer against the source themselves.
 *
 * We deliberately do not auto-cite a manual paragraph: matching heuristics
 * produced citations that pointed at unrelated slides, and a wrong citation is
 * worse than none for someone deciding whether to trust the bank. Instead we
 * offer the two things that are exact — the original PDF for that chapter, and a
 * prefilled full-text search for the answer's distinctive terms.
 */
export default function VerifySource({ question, chapter, pdfUrl, onSearch }) {
  const [open, setOpen] = useState(false)
  if (!question) return null

  const ci = question.correctIndex
  const correct = ci != null && question.options?.[ci] ? question.options[ci] : ''
  const anchor = question.anchor?.snippet ? question.anchor : null

  const term = (() => {
    const words = correct
      .replace(/[^A-Za-z0-9\s-]/g, ' ')
      .split(/\s+/)
      .filter(w => w.length > 5)
    if (words.length >= 2) return words.slice(0, 3).join(' ')
    return question.stem.split(/\s+/).slice(0, 4).join(' ')
  })()

  return (
    <div className="verify-source">
      <button type="button" className="verify-toggle" aria-expanded={open} onClick={() => setOpen(o => !o)}>
        <FileText size={14} /> Verify this answer in the source
        <ChevronDown size={14} className={open ? 'rot' : ''} />
      </button>
      {open && (
        <div className="verify-body">
          {anchor && (
            <p className="verify-anchor">
              <span className="label">Closest manual section</span>
              <strong>{anchor.section}</strong>
              <span className="verify-quote">“{anchor.snippet}”</span>
            </p>
          )}
          <div className="verify-actions">
            {pdfUrl && (
              <a className="btn ghost verify-btn" href={pdfUrl} target="_blank" rel="noreferrer">
                <ExternalLink size={14} /> Original PDF, {chapter ? `Chapter ${chapter.number}` : 'this chapter'}
              </a>
            )}
            <button type="button" className="btn ghost verify-btn" onClick={() => onSearch?.(term)}>
              <Search size={14} /> Search manual for “{term}”
            </button>
          </div>
          <p className="small muted verify-note">
            The answer key and manual text are the source of truth. If this rationale looks wrong,
            trust the manual — and say so, because a bad item should be fixed, not memorised.
          </p>
        </div>
      )}
    </div>
  )
}
