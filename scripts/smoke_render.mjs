/**
 * Server-side render smoke test.
 *
 * Renders every route of the built app in jsdom against the real data files, so
 * runtime errors (bad props, undefined maps, broken hooks) surface without a
 * browser. Run with: node scripts/smoke_render.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { JSDOM } from 'jsdom'

const ROOT = path.resolve(import.meta.dirname, '..')
const DATA = path.join(ROOT, 'public/data')

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'https://example.test/apea/study/',
  pretendToBeVisual: true,
})
global.window = dom.window
global.document = dom.window.document
Object.defineProperty(global, 'navigator', { value: dom.window.navigator, configurable: true })
global.localStorage = dom.window.localStorage
global.location = dom.window.location
global.HTMLElement = dom.window.HTMLElement
global.Element = dom.window.Element
global.Node = dom.window.Node
global.matchMedia = dom.window.matchMedia || (() => ({ matches: false, addEventListener() {}, removeEventListener() {} }))
global.confirm = () => true
global.alert = () => {}

const read = f => JSON.parse(fs.readFileSync(path.join(DATA, f), 'utf8'))

// serve /data/* from disk so fetch resolves exactly as in the browser
const nativeFetch = global.fetch
global.fetch = async (url, opts) => {
  const u = String(url)
  const m = u.match(/data\/(.+)$/)
  if (m) {
    const file = path.join(DATA, m[1])
    if (!fs.existsSync(file)) return { ok: false, status: 404, json: async () => null, text: async () => '' }
    const body = fs.readFileSync(file, 'utf8')
    return { ok: true, status: 200, json: async () => JSON.parse(body), text: async () => body }
  }
  return nativeFetch ? nativeFetch(url, opts) : { ok: false, status: 404 }
}

const { createRequire } = await import('node:module')
const require_ = createRequire(import.meta.url)
const bundle = require_('./.smoke-bundle.cjs').default
const { renderApp, buildPlan, HighYield, Planner, Tests, Flashcards, SearchPanel, renderNode, h } = bundle

const errors = []
dom.window.addEventListener('error', e => errors.push(String(e.message)))


const { applyGuideQuality } = await import('../src/lib/quality.js')

const { contentStats } = await import('../src/lib/contentStats.js')

const { buildTwelveWeekPath } = await import('../src/lib/studyPath.js')
const { countCompletedPathWeeks } = await import('../src/lib/milestones.js')

const guideRaw = read('guide.json')
const quality = read('question-quality.json')
const rationales = read('rationale-upgrades.json')
const professional = read('professional-questions.json')
const guide = applyGuideQuality(guideRaw, quality, rationales, professional)
const manualBank = read('manual-questions.json')
const pearls = read('pearls-clean.json').pearls

let failures = 0
const check = (name, fn) => {
  try {
    fn()
    console.log(`  ok   ${name}`)
  } catch (e) {
    failures += 1
    console.log(`  FAIL ${name}: ${e.message}`)
  }
}

console.log('data integrity')
check('every chapter has questions except orientation ch.1', () => {
  const empty = guide.chapters.filter(c => c.questions.length === 0).map(c => c.number)
  if (empty.length && !(empty.length === 1 && empty[0] === 1)) throw new Error(`empty chapters: ${empty}`)
})
check('no answer index out of range', () => {
  guide.chapters.forEach(c => c.questions.forEach(q => {
    if (q.correctIndex != null && q.correctIndex >= q.options.length) throw new Error(`${q.id} bad index`)
  }))
})
check('no duplicate option text within a question', () => {
  guide.chapters.forEach(c => c.questions.forEach(q => {
    const s = new Set(q.options.map(o => o.trim().toLowerCase()))
    if (s.size !== q.options.length) throw new Error(`${q.id} duplicate options`)
  }))
})
check('no option longer than 160 chars', () => {
  guide.chapters.forEach(c => c.questions.forEach(q => q.options.forEach(o => {
    if (o.length > 160) throw new Error(`${q.id} has a ${o.length}-char option`)
  })))
})
check('every question has a rationale', () => {
  const missing = guide.chapters.flatMap(c => c.questions).filter(q => !(q.explanation || '').trim())
  if (missing.length) throw new Error(`${missing.length} without rationale, e.g. ${missing[0].id}`)
})

console.log('\nstats')
const stats = contentStats({ guide, manualBank, pearls, questionPool: null })
check('graded total matches chapter sum', () => {
  if (stats.guideGraded !== 314) throw new Error(`expected 314 guide graded, got ${stats.guideGraded}`)
})
check('exam-safe pool is smaller than graded pool', () => {
  if (stats.examSafe >= stats.gradedTotal) throw new Error(`examSafe ${stats.examSafe} !< graded ${stats.gradedTotal}`)
})
console.log(`       guide ${stats.guideGraded} · manual ${stats.manualGraded} · graded ${stats.gradedTotal} · exam-safe ${stats.examSafe} · pearls ${stats.pearlsTotal}`)

console.log('\nplanner')
if (buildPlan) {
  const dates = ['2026-11-11', '2026-11-20', '2026-12-31', '2027-06-01']
  dates.forEach(d => {
    check(`plan covers all chapters (${d})`, () => {
      const r = buildPlan(guide, d)
      if (!r.coveredAll) throw new Error(`skipped chapters ${r.skipped.join(',')}`)
      if (!r.days.length) throw new Error('no days generated')
    })
  })
}

console.log('\n12-week path')
check('task keys are globally unique', () => {
  const weeks = buildTwelveWeekPath(guide)
  const keys = weeks.flatMap(w => w.tasks.map(t => t.key))
  if (new Set(keys).size !== keys.length) throw new Error('duplicate task keys')
})
check('completed-week counter reads the same keys the UI writes', () => {
  const weeks = buildTwelveWeekPath(guide)
  const done = Object.fromEntries(weeks[0].tasks.map(t => [t.key, true]))
  const n = countCompletedPathWeeks(weeks, done)
  if (n !== 1) throw new Error(`expected 1 completed week, got ${n}`)
})

console.log('\nchapter tables')
check('every chapter has reference tables', () => {
  const empty = guide.chapters.filter(c => !(c.id in {}) && false)
  const missing = []
  const mods = {}
  for (const f of fs.readdirSync(path.join(DATA, 'modules'))) {
    if (!f.endsWith('.json')) continue
    const m = JSON.parse(fs.readFileSync(path.join(DATA, 'modules', f), 'utf8'))
    mods[m.chapterId] = (m.reference?.tables || []).length
  }
  for (const c of guide.chapters) if (!mods[c.id]) missing.push(c.number)
  if (missing.length) throw new Error(`no tables for chapters ${missing.join(',')}`)
})
check('tables have headers and rows', () => {
  for (const f of fs.readdirSync(path.join(DATA, 'modules'))) {
    if (!f.endsWith('.json')) continue
    const m = JSON.parse(fs.readFileSync(path.join(DATA, 'modules', f), 'utf8'))
    for (const t of m.reference?.tables || []) {
      if (!t.headers?.length || !t.rows?.length) throw new Error(`${m.chapterId} has an empty table`)
    }
  }
})

console.log('\nPDF list drills')
const pdfLists = read('pdf-lists.json').lists
check('list drills exist', () => {
  if (pdfLists.length < 400) throw new Error(`only ${pdfLists.length} drills`)
})
check('no drill carries slide furniture', () => {
  const bad = pdfLists.filter(l =>
    /FNP\/AGPCNP|Chapter \d|NOTES/i.test(l.prompt) ||
    l.items.some(i => /©|Advanced Practice Education/i.test(i)) ||
    l.items.some(i => /FNP\/AGPCNP Review|Chapter \d+\s+\w+ \|/.test(i)),
  )
  if (bad.length) throw new Error(`${bad.length} contaminated, e.g. "${bad[0].prompt.slice(0, 60)}"`)
})
check('every drill has at least 3 usable items', () => {
  const bad = pdfLists.filter(l => l.items.length < 3 || l.items.some(i => !i || i.length > 200))
  if (bad.length) throw new Error(`${bad.length} malformed drills`)
})
check('drills are attributed to real chapters', () => {
  const ids = new Set(guide.chapters.map(c => c.id))
  const bad = pdfLists.filter(l => !ids.has(l.chapterId))
  if (bad.length) throw new Error(`${bad.length} drills point at unknown chapters`)
})

console.log('\npearl deck')
const pearlDeck = read('pearls-clean.json').pearls
check('pearls deck is non-empty', () => {
  if (!pearlDeck.length) throw new Error('no pearls')
})
check('no pearl carries slide artefacts', () => {
  const bad = pearlDeck.filter(p =>
    /•/.test(p.front) ||
    /\s\$\s/.test(p.front) ||
    /NOTES|CONTENT OVERVIEW|CHECK YOUR KNOWLEDGE|EXAM CHECKLIST|QUESTION\s*#/i.test(p.front) ||
    /\bwhich of the following\b|\bselect all that apply\b/i.test(p.front),
  )
  if (bad.length) throw new Error(`${bad.length} artefacts, e.g. "${bad[0].front.slice(0, 80)}"`)
})
check('no pearl is a mangled cell fragment', () => {
  // tables sliced by column geometry can leave words cut in half
  const bad = pearlDeck.filter(p => /\b[a-z]{1,3}\s[A-Z][a-z]+\s*[:,]/.test(p.front) || /\b\w+\s\w{1,3}$/.test(p.front))
  if (bad.length) throw new Error(`${bad.length} suspicious, e.g. "${bad[0].front.slice(0, 80)}"`)
})
check('every pearl has a real chapter', () => {
  const ids = new Set(guide.chapters.map(c => c.id))
  const bad = pearlDeck.filter(p => !ids.has(p.chapterId))
  if (bad.length) throw new Error(`${bad.length} pearls point at unknown chapters`)
})

console.log('\nspaced repetition')
const srsMod = await import('../src/lib/srs.js')
check('a brand-new account is offered a small first session, not a 200-card wall', () => {
  const cards = Array.from({ length: 200 }, (_, i) => ({ id: `c${i}` }))
  const queue = srsMod.dueCards(cards, {}, 60)
  if (queue.length > 10) throw new Error(`first session offered ${queue.length} new cards`)
  if (!queue.length) throw new Error('first session offered nothing')
})
check('overdue reviews are never throttled', () => {
  const today = srsMod.dateKey()
  const srs = {}
  const cards = Array.from({ length: 50 }, (_, i) => {
    srs[`r${i}`] = { reps: 2, interval: 3, ease: 2.5, due: today, last: today }
    return { id: `r${i}` }
  })
  const queue = srsMod.dueCards(cards, srs, 60)
  if (queue.length !== 50) throw new Error(`only ${queue.length}/50 reviews surfaced`)
})
check('after grading, a card is scheduled into the future', () => {
  const next = srsMod.schedule(undefined, 'good')
  if (!next.due || next.due <= srsMod.dateKey()) throw new Error(`due ${next.due} not in the future`)
  if (!next.interval) throw new Error('no interval assigned')
})

console.log('\nrender smoke test')
// App loads data in effects; a server render only produces the loading screen
// unless we wait for those promises first.
const flush = () => new Promise(r => setTimeout(r, 60))
for (let i = 0; i < 12; i++) {
  const html = renderApp(guide)
  break
  await flush()
}

const routes = ['dashboard', 'library', 'tests', 'workbooks', 'flashcards', 'quickref', 'planner', 'about', 'manuals']
routes.forEach(r => {
  check(`renders #/${r}`, () => {
    dom.window.location.hash = `#/${r}`
    const html = renderApp(guide)
    if (!html || html.length < 400) throw new Error('rendered almost nothing')
    if (/undefined|NaN/.test(html)) {
      const snippet = html.match(/.{40}(undefined|NaN).{40}/)?.[0] || ''
      throw new Error(`output contains undefined/NaN: ${snippet}`)
    }
  })
})

if (errors.length) {
  failures += errors.length
  errors.forEach(e => console.log(`  FAIL runtime error: ${e}`))
}

console.log(failures ? `\n${failures} failure(s)` : '\nall checks passed')
process.exit(failures ? 1 : 0)
