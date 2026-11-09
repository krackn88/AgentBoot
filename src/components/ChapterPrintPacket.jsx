import React from 'react'
import { Blocks } from './Reader.jsx'

/**
 * Printable study packet: condensed guide, pearls, reference tables, and a
 * practice sheet with an answer key.
 *
 * The practice section used to print only the stem and an "Answer: _____" line,
 * so a student had no options to choose from — the worksheet could not be filled
 * in. Options are now printed, and the page shows a short-answer space for the
 * rationale rather than pretending this is a bubble sheet.
 */
export default function ChapterPrintPacket({ chapter, module, pearls: reviewedPearls = [] }) {
  const graded = chapter.questions.filter(q => q.correctIndex != null && q.options?.length >= 2)
  const practice = graded.slice(0, 12)
  const tables = module?.reference?.tables ?? []
  // reviewed deck only; module.pearls is the old keyword extraction
  const pearls = reviewedPearls.map(p => p.front || p)

  return (
    <div className="chapter-print-packet">
      <header className="packet-cover">
        <p className="eyebrow">APEA 2026 FNP · Study packet</p>
        <h1>Chapter {chapter.number}: {chapter.shortTitle}</h1>
        <p className="muted">
          Condensed guide · {pearls.length} clinical pearls · {tables.length} reference tables · {graded.length} practice items
        </p>
        <p className="small muted">Name: _________________________ Date: __________</p>
      </header>

      <section>
        <h2>Study guide</h2>
        {chapter.sections.map(sec => (
          <div key={sec.id} className="packet-section">
            <h3>{sec.title}</h3>
            <Blocks blocks={sec.blocks} />
          </div>
        ))}
      </section>

      {tables.length > 0 && (
        <section className="page-break-before">
          <h2>Reference tables</h2>
          {tables.map((t, i) => (
            <div key={i} className="packet-section">
              <p className="label">{t.section}</p>
              <table className="packet-table">
                <thead><tr>{t.headers.map((h, j) => <th key={j}>{h}</th>)}</tr></thead>
                <tbody>{t.rows.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{c}</td>)}</tr>)}</tbody>
              </table>
            </div>
          ))}
        </section>
      )}

      {pearls.length > 0 && (
        <section className="page-break-before">
          <h2>Clinical pearls</h2>
          <ol className="packet-pearls">
            {pearls.map((p, i) => <li key={i}>{p}</li>)}
          </ol>
        </section>
      )}

      {practice.length > 0 && (
        <section className="page-break-before">
          <h2>Practice questions</h2>
          <p className="small muted">Circle one letter, then write the reason in a sentence — the reasoning is what the exam tests.</p>
          {practice.map((q, i) => (
            <div key={q.id} className="packet-q">
              <p><strong>{i + 1}.</strong> {q.stem}</p>
              <ol className="packet-options" type="A">
                {q.options.map((o, j) => <li key={j}>{o}</li>)}
              </ol>
              <div className="packet-blank">Answer: _____ Why: _________________________________________</div>
            </div>
          ))}
        </section>
      )}

      {practice.length > 0 && (
        <section className="page-break-before packet-answers">
          <h2>Answer key</h2>
          {practice.map((q, i) => (
            <p key={q.id} className="small">
              <strong>{i + 1}. {String.fromCharCode(65 + q.correctIndex)}.</strong>{' '}
              {q.options[q.correctIndex]}
              {q.explanation ? ` — ${q.explanation.length > 240 ? q.explanation.slice(0, 240) + '…' : q.explanation}` : ''}
            </p>
          ))}
          {graded.length > practice.length && (
            <p className="small muted">
              {graded.length - practice.length} more questions for this chapter are in the question bank.
            </p>
          )}
        </section>
      )}
    </div>
  )
}
