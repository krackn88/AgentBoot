/**
 * Content readability gate.
 *
 * Three separate screens shipped the same defect: a bare table cell presented as a
 * question ("Itch / HIVES? / Intense", "Live vaccines"). The root cause was content
 * reaching the UI without anyone checking that it reads as a question.
 *
 * This module defines what "reads as a question" means, in one place, so the smoke
 * suite can assert it for every card and drill the site generates.
 */

const MIN_PROMPT_WORDS = 5
const MAX_PROMPT_CHARS = 180

// A prompt must open with an interrogative or an instruction verb.
const QUESTION_OPENER =
  /^(what|which|who|when|where|why|how|name|list|describe|identify|define|explain|match|state|recall|complete|fill in the blank|in |for )/i

// A bare noun phrase such as "Live vaccines" or "Itch" is not a question.
const BARE_NOUN_PHRASE = /^[A-Za-z0-9"'()\-–/ ]{1,40}$/

export function promptIssues(prompt) {
  const p = (prompt || '').trim()
  const issues = []
  if (!p) {
    issues.push('empty')
    return issues
  }
  if (p.length > MAX_PROMPT_CHARS) issues.push('too long')
  const words = p.split(/\s+/)
  if (words.length < MIN_PROMPT_WORDS) issues.push(`only ${words.length} words`)
  if (!QUESTION_OPENER.test(p)) issues.push('does not open as a question or instruction')
  if (!p.endsWith('?') && !p.endsWith('.')) issues.push('no terminal punctuation')
  if (BARE_NOUN_PHRASE.test(p) && !p.endsWith('?')) issues.push('bare noun phrase')
  if (/^(yes|no|true|false)$/i.test(p)) issues.push('not a question')
  return issues
}

export function answerIssues(answer) {
  const a = (answer || '').trim()
  const issues = []
  if (!a) issues.push('empty answer')
  if (/\bundefined\b|\bNaN\b/i.test(a)) issues.push('placeholder text')
  if (a.length > 400) issues.push('answer too long for a card')
  return issues
}

/** Audit a batch of cards: returns only the failures, with reasons. */
export function auditCards(cards, label = 'card') {
  const failures = []
  cards.forEach(c => {
    const problems = [...promptIssues(c.front ?? c.prompt), ...answerIssues(c.back ?? c.answer)]
    if (problems.length) {
      failures.push({ label, prompt: (c.front ?? c.prompt ?? '').slice(0, 90), problems })
    }
  })
  return failures
}

/** Percentage of a batch that reads cleanly, plus sample failures. */
export function readabilityReport(cards, label = 'card') {
  const failures = auditCards(cards, label)
  const total = cards.length
  return {
    label,
    total,
    clean: total - failures.length,
    percent: total ? Math.round(((total - failures.length) / total) * 100) : 100,
    examples: failures.slice(0, 5),
  }
}
