/**
 * SM-2 style spaced repetition, tuned for board prep (short horizons, dense facts).
 *
 * State per card lives in store.srs[cardId]:
 *   { ease, interval, reps, lapses, due (ISO date), last (ISO date) }
 *
 * Grades are the three buttons a tired student can actually use:
 *   'again'  — blanked or wrong      → relearn today, ease down
 *   'hard'   — got it, but slowly    → short interval
 *   'good'   — knew it cold          → normal interval growth
 */

export const DAY_MS = 86400000
export const GRADES = [
  { id: 'again', label: 'Again', hint: 'Missed it', key: '1' },
  { id: 'hard', label: 'Hard', hint: 'Slow recall', key: '2' },
  { id: 'good', label: 'Good', hint: 'Knew it', key: '3' },
]

export function dateKey(d = new Date()) {
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

export function addDays(n, from = new Date()) {
  return dateKey(new Date(from.getTime() + n * DAY_MS))
}

export function isNew(state) {
  return !state || !state.reps
}

export function isDue(state, today = dateKey()) {
  if (isNew(state)) return true
  return (state.due || today) <= today
}

/**
 * Next scheduling state for a card.
 * @param {object|undefined} prev previous srs entry
 * @param {'again'|'hard'|'good'} grade
 */
export function schedule(prev, grade) {
  const today = dateKey()
  const s = prev || { ease: 2.5, interval: 0, reps: 0, lapses: 0, due: today, last: null }

  if (grade === 'again') {
    return {
      ease: Math.max(1.3, s.ease - 0.2),
      interval: 0,
      reps: 0,
      lapses: (s.lapses || 0) + 1,
      due: today,
      last: today,
    }
  }

  const ease = grade === 'hard' ? Math.max(1.3, s.ease - 0.15) : Math.min(3.2, s.ease + 0.05)
  let interval
  if (grade === 'hard') {
    interval = s.interval ? Math.max(1, Math.round(s.interval * 1.2)) : 1
  } else if (!s.reps) {
    interval = 1
  } else if (s.reps === 1) {
    interval = 3
  } else {
    interval = Math.max(1, Math.round(s.interval * ease))
  }

  return {
    ease,
    interval,
    reps: (s.reps || 0) + 1,
    lapses: s.lapses || 0,
    due: addDays(interval),
    last: today,
  }
}

/** Cards to study now: everything due (or new), capped. */
/** Split a pool into genuinely-due reviews and never-seen cards. */
export function splitDue(cards, srs, today = dateKey()) {
  const reviews = []
  const fresh = []
  cards.forEach(c => {
    const st = srs[c.id]
    if (!st || !st.reps) fresh.push(c)
    else if ((st.due || today) <= today) reviews.push(c)
  })
  reviews.sort((a, b) => String(srs[a.id].due).localeCompare(String(srs[b.id].due)))
  return { reviews, fresh }
}

/**
 * The queue to study now: overdue reviews first, then new cards up to a daily cap.
 *
 * Unseen cards used to be merged into "due", so a brand-new account was told to
 * "clear 200 due cards" — a wall nobody starts against. Reviews are always
 * included (they decay); new material is throttled.
 */
export function dueCards(cards, srs, limit = 40, today = dateKey(), newLimit = 10) {
  const { reviews, fresh } = splitDue(cards, srs, today)
  return [...reviews, ...fresh.slice(0, newLimit)].slice(0, limit)
}

export function deckStats(cards, srs, today = dateKey()) {
  let learned = 0
  let dueNow = 0
  let mature = 0
  cards.forEach(c => {
    const st = srs[c.id]
    if (st?.reps) {
      learned++
      if ((st.due || today) <= today) dueNow++
      if (st.interval >= 21) mature++
    }
  })
  return { total: cards.length, learned, dueNow, mature, fresh: cards.length - learned }
}

/** 14-day review forecast for the deck header sparkline. */
export function forecast(cards, srs, days = 14) {
  const today = dateKey()
  const buckets = Array.from({ length: days }, () => 0)
  cards.forEach(c => {
    const st = srs[c.id]
    if (!st?.reps) return
    const diff = Math.round((new Date(st.due) - new Date(today)) / DAY_MS)
    if (diff >= 0 && diff < days) buckets[diff]++
    else if (diff < 0) buckets[0]++
  })
  return buckets
}
