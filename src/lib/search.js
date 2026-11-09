/**
 * Search over the full content index (guide + manuals + pearls + questions).
 *
 * The static host doesn't gzip, so the index ships dictionary-encoded and split:
 *   search-chunks/manifest.json  chapters, sections, chunk list
 *   search-chunks/core.json      guide sections, pearls, questions (~500 KB)
 *   search-chunks/manual.json    every manual line (~600 KB, loaded in background)
 *
 * Core loads on first search so results appear immediately; the manual chunk
 * streams in behind it and results refresh when it lands.
 */

const BASE = () => import.meta.env.BASE_URL
const URL_MANIFEST = () => `${BASE()}data/search-chunks/manifest.json`
const URL_CHUNK = (name) => `${BASE()}data/search-chunks/${name}.json`

const decode = (rows, manifest) => {
  const kinds = Object.fromEntries(Object.entries(manifest.kinds).map(([k, v]) => [v, k]))
  return rows.map(([c, s, k, x]) => ({
    c: manifest.chapters[c]?.id || '',
    t: manifest.chapters[c]?.title || '',
    s: manifest.sections[s] || '',
    k: kinds[k] || 'guide',
    x,
  }))
}

let state = null
let booting = null

export function loadSearchIndex(onUpdate) {
  if (state?.complete) {
    onUpdate?.(state.docs, { complete: true })
    return Promise.resolve(state.docs)
  }
  if (booting) return booting

  booting = fetch(URL_MANIFEST())
    .then(r => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
    .then(async manifest => {
      const core = await fetch(URL_CHUNK('core')).then(r => r.json())
      state = { manifest, docs: decode(core.rows, manifest), complete: false }
      onUpdate?.(state.docs, { complete: false })

      // stream the manual text in behind the first results
      fetch(URL_CHUNK('manual'))
        .then(r => r.json())
        .then(manual => {
          state.docs = state.docs.concat(decode(manual.rows, manifest))
          state.complete = true
          onUpdate?.(state.docs, { complete: true })
        })
        .catch(() => {
          state.complete = true
          onUpdate?.(state.docs, { complete: true })
        })

      booting = null
      return state.docs
    })
    .catch(e => {
      booting = null
      throw e
    })

  return booting
}

/** Crude but effective clinical stemming: strip plurals and common suffixes. */
function stem(word) {
  const w = word.toLowerCase()
  if (w.length > 5 && w.endsWith('ies')) return w.slice(0, -3) + 'y'
  if (w.length > 4 && w.endsWith('es')) return w.slice(0, -2)
  if (w.length > 3 && w.endsWith('s') && !w.endsWith('ss')) return w.slice(0, -1)
  return w
}

/** "CURB-65" should match "CURB 65" and vice versa. */
function normalise(text) {
  return text.toLowerCase().replace(/[–—]/g, '-')
}

export function buildNeedle(query) {
  const q = query.trim()
  if (q.length < 2) return null
  const terms = normalise(q)
    .split(/[^a-z0-9.\-+]+/)
    .filter(t => t.length >= 2)
    .map(stem)
  if (!terms.length) return null
  return { raw: q, phrase: normalise(q).replace(/\s+/g, ' '), terms }
}

const KIND_WEIGHT = { pearl: 1.5, rationale: 1.35, question: 1.2, guide: 1.1, manual: 1.0 }

export function searchDocs(docs, query, limit = 40) {
  const needle = buildNeedle(query)
  if (!needle || !docs) return []
  const { phrase, terms } = needle
  const results = []

  for (const doc of docs) {
    const hay = doc._hay || (doc._hay = normalise(doc.x))
    const titleHay = normalise(`${doc.s} ${doc.t}`)

    const phraseHit = phrase.length >= 4 && hay.includes(phrase)
    let matched = 0
    let titleHits = 0
    for (const t of terms) {
      if (hay.includes(t)) matched++
      else if (t.length > 4 && hay.includes(t.slice(0, Math.max(4, t.length - 2)))) matched += 0.6
      if (titleHay.includes(t)) titleHits++
    }
    if (!matched) continue

    const coverage = matched / terms.length
    if (coverage < 0.6) continue

    const pos = hay.indexOf(terms[0])
    const early = pos >= 0 && pos < 80 ? 1.15 : 1
    const score = (phraseHit ? 3 : 0) + coverage * 2 + titleHits * 0.7 + (KIND_WEIGHT[doc.k] || 1) * early

    results.push({ doc, score })
  }

  results.sort((a, b) => b.score - a.score || a.doc.x.length - b.doc.x.length)
  return results.slice(0, limit).map(r => r.doc)
}

/** Split text for highlight rendering: [{text, hit}] */
export function highlight(text, query) {
  const needle = buildNeedle(query)
  if (!needle) return [{ text, hit: false }]
  const parts = needle.terms.filter(t => t.length > 2).map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  if (!parts.length) return [{ text, hit: false }]
  const re = new RegExp(`(${parts.join('|')})`, 'gi')
  const out = []
  let last = 0
  let m
  while ((m = re.exec(text))) {
    if (m.index > last) out.push({ text: text.slice(last, m.index), hit: false })
    out.push({ text: m[0], hit: true })
    last = m.index + m[0].length
    if (re.lastIndex === m.index) re.lastIndex++
  }
  if (last < text.length) out.push({ text: text.slice(last), hit: false })
  return out
}
