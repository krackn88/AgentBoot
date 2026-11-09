/** Merge guide questions, manual-bank items, and JSON supplements into one pool. */
export function applySupplements(guide, supplements) {
  if (!supplements?.patches?.length) return guide
  const patch = Object.fromEntries(supplements.patches.map(p => [p.id, p]))
  const chapters = guide.chapters.map(ch => ({
    ...ch,
    questions: [
      ...ch.questions.map(q => {
        const p = patch[q.id]
        if (!p) return q
        return {
          ...q,
          options: p.options ?? q.options,
          correctIndex: p.correctIndex ?? q.correctIndex,
          explanation: p.explanation ?? q.explanation,
        }
      }),
      ...(supplements.extra || []).filter(e => e.chapterId === ch.id),
    ],
  }))
  return { ...guide, chapters }
}

export function flattenQuestions(guide, manualBank = null) {
  const fromGuide = guide.chapters.flatMap(c =>
    c.questions.map(q => ({ ...q, chapterTitle: c.shortTitle, source: q.source || 'guide' }))
  )
  const fromManual = (manualBank?.questions || []).map(q => ({
    ...q,
    chapterTitle: q.chapterTitle || q.chapterId,
    source: 'manual',
  }))
  return [...fromGuide, ...fromManual]
}

export function gradable(questions) {
  return questions.filter(q => q.correctIndex != null && (q.options?.length ?? 0) >= 2)
}
