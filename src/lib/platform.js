/** Single source for static JSON adjacent to the study guide (dedupes App.jsx fetches). */

const base = () => import.meta.env.BASE_URL

const cache = new Map()

async function fetchJson(path, fallback) {
  const url = `${base()}${path}`
  if (cache.has(url)) return cache.get(url)
  const p = fetch(url)
    .then(r => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
    .catch(e => {
      cache.delete(url)
      if (fallback !== undefined) return fallback
      throw e
    })
  cache.set(url, p)
  return p
}

export function loadGuide() {
  return fetchJson('data/guide.json')
}

export function loadPlatformBundle() {
  return Promise.all([
    fetchJson('data/search-corpus.json', []),
    fetchJson('data/pearls.json', []),
    fetchJson('data/content-index.json', null),
    fetchJson('data/manual-questions.json', null),
  ]).then(([searchCorpus, pearlCards, contentMeta, manualBank]) => ({
    searchCorpus,
    pearlCards,
    contentMeta,
    manualBank,
  }))
}

const moduleCache = new Map()

/** Prefetch chapter module JSON (Reader loads via same path; cache is shared). */
export function prefetchChapterModule(chapterId) {
  if (!chapterId || moduleCache.has(chapterId)) return
  const url = `${base()}data/modules/${chapterId}.json`
  moduleCache.set(chapterId, fetch(url).then(r => (r.ok ? r.json() : null)).catch(() => null))
}

export function loadChapterModule(chapterId) {
  if (moduleCache.has(chapterId)) return moduleCache.get(chapterId)
  const p = fetchJson(`data/modules/${chapterId}.json`)
  moduleCache.set(chapterId, p)
  return p
}
