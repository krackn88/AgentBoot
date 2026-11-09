import React from 'react'

/**
 * Renders one APEA manual's extracted text.
 *
 * These files are PDF layout extracts: the page's columns survive only as runs
 * of spaces. Markdown collapses whitespace, which welds adjacent table columns
 * into single false statements ("NEVER give; risks always outweigh ONLY if
 * benefits outweigh risks..." — two opposite columns). So the text is rendered
 * preformatted: alignment is preserved exactly, nothing is merged or invented.
 *
 * Cleaned, verified tables for each chapter live in the chapter reader's
 * "Course manual depth" tab, which is generated server-side and validated.
 */
export default function ManualContent({ text }) {
  const body = (text || '').replace(/^---[\s\S]*?---\s*/, '')
  return (
    <div className="manual-raw-wrap">
      <p className="manual-raw-note small">
        Raw layout-preserving extract of the source PDF. Columns keep their original alignment, so
        nothing is merged. For cleaned tables, open the chapter&apos;s <strong>Course manual depth</strong> tab,
        or use the original PDF above.
      </p>
      <pre className="manual-raw">{body}</pre>
    </div>
  )
}
