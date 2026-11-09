import React from 'react'
import { Blocks } from './Reader.jsx'

/** Printable study packet: condensed guide + pearls + practice question sheet. */
export default function ChapterPrintPacket({ chapter, module }) {
  const graded = chapter.questions.filter(q => q.correctIndex != null && q.options?.length >= 2)
  const practice = graded.slice(0, 12)
  return (
    <div className="chapter-print-packet">
      <header className="packet-cover">
        <p className="eyebrow">APEA 2026 FNP · Study packet</p>
        <h1>Chapter {chapter.number}: {chapter.shortTitle}</h1>
        <p className="muted">Condensed guide · {module?.pearls?.length || 0} clinical pearls · {graded.length} practice items</p>
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

      {module?.pearls?.length > 0 && (
        <section className="page-break-before">
          <h2>Clinical pearls</h2>
          <ol className="packet-pearls">
            {module.pearls.map((p, i) => <li key={i}>{p}</li>)}
          </ol>
        </section>
      )}

      {practice.length > 0 && (
        <section className="page-break-before">
          <h2>Practice questions — write your answer letter</h2>
          {practice.map((q, i) => (
            <div key={q.id} className="packet-q">
              <p><strong>{i + 1}.</strong> {q.stem}</p>
              <div className="packet-blank">Answer: _____</div>
            </div>
          ))}
        </section>
      )}

      {practice.length > 0 && (
        <section className="page-break-before packet-answers">
          <h2>Answer key</h2>
          {practice.map((q, i) => (
            <p key={q.id} className="small"><strong>{i + 1}.</strong> {String.fromCharCode(65 + q.correctIndex)}. {q.options[q.correctIndex]}{q.explanation ? ` — ${q.explanation.slice(0, 200)}` : ''}</p>
          ))}
        </section>
      )}
    </div>
  )
}
