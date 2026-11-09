/**
 * Which questions may appear in a *graded* timed exam.
 *
 * Manual-slide MCQs only qualify when their answer was established rather than
 * guessed: `override` (curated by hand) or `guide-match` (cross-walked to the
 * study guide's Answer Key). The `inferred` items were scored by text overlap
 * alone, and spot checks found answers like "B12 and folate levels" keyed to a
 * rash question — grading someone wrong on a bad key is worse than a shorter
 * exam, so they are excluded here while still being usable for casual practice.
 */
const VERIFIED_MANUAL_GRADING = ['override', 'guide-match', 'corpus-rescore']

export function examUsable(q) {
  if (q.correctIndex == null || (q.options?.length ?? 0) < 2) return false
  if (q.duplicateOf) return false
  if (q.source === 'manual') return VERIFIED_MANUAL_GRADING.includes(q.grading)
  return true
}

export function examPool(pool) {
  return pool.filter(examUsable)
}
