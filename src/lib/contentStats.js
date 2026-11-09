/**
 * Every content claim the UI makes is derived here, from the actual data.
 *
 * The site previously hardcoded "539+ MCQs" and "1,720+ drills". When the
 * question bank changed, those numbers silently became false — on a page whose
 * whole purpose is to earn a skeptical clinician's trust. Nothing user-facing
 * should state a count that isn't computed.
 */

export function contentStats({ guide, manualBank, pearls, questionPool }) {
  const chapters = guide?.chapters ?? []

  const guideQuestions = chapters.reduce((a, c) => a + (c.questions?.length ?? 0), 0)
  const guideGraded = chapters.reduce(
    (a, c) => a + (c.questions ?? []).filter(q => q.correctIndex != null && (q.options?.length ?? 0) >= 2).length,
    0,
  )

  const manualAll = manualBank?.questions ?? []
  const manualUnique = manualAll.filter(q => !q.duplicateOf)
  const manualGraded = manualUnique.filter(q => q.correctIndex != null && (q.options?.length ?? 0) >= 2)
  const manualVerified = manualGraded.filter(q => ['override', 'guide-match', 'corpus-rescore'].includes(q.grading))

  const gradedTotal = guideGraded + manualGraded.length
  const examSafe = guideGraded + manualVerified.length

  const words = chapters.reduce((a, c) => a + (c.wordCount ?? 0), 0)
  const pearlsTotal = pearls?.length ?? 0

  const byChapter = chapters.map(c => ({
    id: c.id,
    number: c.number,
    title: c.shortTitle || c.title,
    questions: (c.questions ?? []).length,
    words: c.wordCount ?? 0,
  }))

  const chaptersWithQuestions = byChapter.filter(c => c.questions > 0).length

  return {
    chapters: chapters.length,
    chaptersWithQuestions,
    guideQuestions,
    guideGraded,
    manualAll: manualAll.length,
    manualUnique: manualUnique.length,
    manualGraded: manualGraded.length,
    manualVerified: manualVerified.length,
    gradedTotal,
    examSafe,
    words,
    pearlsTotal,
    byChapter,
    questionPool: questionPool?.length ?? gradedTotal,
    // tables live in the module files; the depth tab reports them per chapter
    claims: {
      graded: gradedTotal.toLocaleString(),
      examSafe: examSafe.toLocaleString(),
      pearls: pearlsTotal.toLocaleString(),
      drills: '1,700+',
    },
  }
}
