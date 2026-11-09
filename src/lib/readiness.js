/**
 * Readiness is a study tracker, not a prediction of a board score.
 * Three components, weighted, each shown separately so the number is auditable:
 *   coverage (40%)  — chapters marked complete
 *   practice (35%)  — breadth of questions attempted × accuracy
 *   retention (25%) — flashcards that reached a 21-day interval
 *
 * Breadth uses a target (not the whole pool) because nobody finishes 539 items;
 * hitting the target with good accuracy is what correlates with readiness.
 */
import { deckStats } from './srs'

export const TARGET_QUESTIONS = 300
export const WEIGHTS = { coverage: 0.4, practice: 0.35, retention: 0.25 }

export function computeReadiness({ doneCh, totalCh, answered, accuracy, cards, srs }) {
  const coverage = totalCh ? Math.min(1, doneCh / totalCh) : 0

  const breadth = Math.min(1, answered / TARGET_QUESTIONS)
  // accuracy below 50% contributes little; 75%+ is full credit
  const quality = answered ? Math.max(0, Math.min(1, (accuracy - 50) / 25)) : 0
  const practice = answered ? breadth * quality : 0

  const { mature, total } = deckStats(cards || [], srs || {})
  const retention = total ? Math.min(1, mature / Math.max(60, total * 0.35)) : 0

  const score = Math.round(
    (coverage * WEIGHTS.coverage + practice * WEIGHTS.practice + retention * WEIGHTS.retention) * 100,
  )

  const parts = [
    {
      id: 'coverage',
      label: 'Chapter coverage',
      weight: WEIGHTS.coverage,
      value: coverage,
      detail: `${doneCh} of ${totalCh} chapters marked complete`,
      action: doneCh < totalCh ? 'Read the next unopened chapter' : 'All chapters complete',
      go: 'library',
    },
    {
      id: 'practice',
      label: 'Practice breadth & accuracy',
      weight: WEIGHTS.practice,
      value: practice,
      detail: answered
        ? `${answered} questions tried at ${accuracy}% · target ${TARGET_QUESTIONS}`
        : 'No questions answered yet',
      action: answered < TARGET_QUESTIONS ? 'Work through a chapter quiz' : 'Drill your missed questions',
      go: 'quiz',
    },
    {
      id: 'retention',
      label: 'Retention (spaced review)',
      weight: WEIGHTS.retention,
      value: retention,
      detail: `${mature} cards mastered to a 21-day interval`,
      action: 'Clear today’s due cards',
      go: 'flashcards',
    },
  ]

  const weakest = [...parts].sort((a, b) => a.value - b.value)[0]

  return {
    score,
    parts,
    weakest,
    // kept for the certificate / export which expect a flat number
    readiness: score,
  }
}
