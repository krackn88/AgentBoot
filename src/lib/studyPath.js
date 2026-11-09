/** Default 12-week board prep arc (before user sets a custom exam date). */
export function buildTwelveWeekPath(guide) {
  const chapters = guide.chapters
  const weeks = []
  const perWeek = Math.ceil(chapters.length / 12)
  for (let w = 0; w < 12; w++) {
    const slice = chapters.slice(w * perWeek, (w + 1) * perWeek)
    if (!slice.length) continue
    const ids = slice.map(c => c.id)
    const focus = slice.map(c => c.shortTitle).join(', ')
    const tasks = [
      { key: `w${w}-read`, label: 'Read & annotate', detail: `Chapters ${slice[0].number}–${slice[slice.length - 1].number}: ${focus}` },
      { key: `w${w}-wb`, label: 'Workbook drills', detail: 'Complete table recall + pearl drills for this block' },
      { key: `w${w}-quiz`, label: 'Chapter quizzes', detail: `Grade all practice questions in chapters ${slice[0].number}–${slice[slice.length - 1].number}` },
    ]
    if (w === 3 || w === 7 || w === 11) tasks.push({ key: `w${w}-mock`, label: 'Timed mock', detail: w === 11 ? 'Full-length AANP simulation' : 'Mock Board A or Manual Mock A' })
    if (w === 11) tasks.push({ key: `w${w}-hy`, label: 'High-yield cram', detail: 'Quick reference + clinical pearl flashcards until mastered' })
    weeks.push({ week: w + 1, chapterIds: ids, tasks })
  }
  return weeks
}
