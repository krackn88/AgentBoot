const TOAST_KEY = 'apea-milestone-toasts'

export const MILESTONE_DEFS = [
  { id: 'first-quiz', label: 'First questions', emoji: '✓', desc: 'Answered your first practice questions', when: (c) => c.answered >= 5 },
  { id: 'first-mock', label: 'Mock starter', emoji: '🏁', desc: 'Finished a timed mock exam', when: (c) => c.mockCount >= 1 },
  { id: 'chapters-half', label: 'Half the guide', emoji: '📖', desc: 'Completed 50%+ of chapters', when: (c) => c.totalCh > 0 && c.doneCh / c.totalCh >= 0.5 },
  { id: 'streak-7', label: 'Week streak', emoji: '🔥', desc: '7-day study streak', when: (c) => c.streak >= 7 },
  { id: 'pearls-50', label: 'Pearl drill', emoji: '💎', desc: '50+ flashcards mastered', when: (c) => c.mastered >= 50 },
  { id: 'readiness-75', label: 'Board ready', emoji: '🎯', desc: '75%+ composite readiness', when: (c) => c.readiness >= 75 },
  { id: 'path-week', label: 'Path week', emoji: '📅', desc: 'Completed a full week on the guided path', when: (c) => c.weeksComplete >= 1 },
]

export function buildMilestoneContext(store, stats, weeksComplete = 0) {
  const mockCount = (store.quizHistory || []).filter(h => h.testId && !String(h.testId).startsWith('ch-')).length
  return { ...stats, mockCount, weeksComplete }
}

export function earnedMilestones(ctx) {
  return MILESTONE_DEFS.filter(m => m.when(ctx))
}

function loadToasted() {
  try { return new Set(JSON.parse(localStorage.getItem(TOAST_KEY) || '[]')) }
  catch { return new Set() }
}

function saveToasted(set) {
  localStorage.setItem(TOAST_KEY, JSON.stringify([...set]))
}

/** Returns newly earned milestone ids to toast (and marks them shown). */
export function popNewMilestoneToasts(ctx) {
  const earned = earnedMilestones(ctx)
  const toasted = loadToasted()
  const fresh = earned.filter(m => !toasted.has(m.id))
  fresh.forEach(m => toasted.add(m.id))
  if (fresh.length) saveToasted(toasted)
  return fresh
}

export function countCompletedPathWeeks(weeks, studyPathDone = {}) {
  // task keys are unique on their own (`w3-read`); do not re-prefix the week
  return weeks.filter(w => w.tasks.every(t => studyPathDone[t.key])).length
}
