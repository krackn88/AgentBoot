# APEA FNP Study Hub — architecture (1-page)

## Runtime model

- **Vite + React** SPA served from `dist/` (hash routes: `#/dashboard`, `#/reader/:chapterId`, …).
- **No backend** for study progress: state lives in `localStorage` via `src/lib/store.js`.
- **Content** is static JSON/Markdown under `public/data/`, built into `dist/data/` at deploy time.

## Data flow

```
public/data/guide.json          → boot (required)
public/data/content-index.json  ┐
public/data/manual-questions.json
public/data/pearls.json         ├→ loadPlatformBundle() in src/lib/platform.js
public/data/search-corpus.json  ┘
public/data/modules/{chapterId}.json → Reader tab + optional prefetch on chapter hover
public/data/manuals/*.md        → Manuals view (lazy)
```

1. `App.jsx` loads `guide.json` first; shows boot screen until ready.
2. `StudyApp` calls `loadPlatformBundle()` once for search, pearls, content depth, and manual MCQ bank.
3. `flattenQuestions(guide, manualBank)` merges guide + manual questions for Quiz, Tests, and flashcards.
4. Readiness score (dashboard) is computed client-side from completions, accuracy, and flashcard mastery.

## Key modules

| Path | Role |
|------|------|
| `src/lib/platform.js` | Cached fetches for guide-adjacent JSON + module prefetch |
| `src/lib/questions.js` | Question pooling and grading helpers |
| `src/lib/readinessReport.js` | Printable readiness export |
| `src/lib/plans.js` | Display-only tiers (`BETA_OPEN` in `config.js` keeps paywall off) |
| `src/components/Tests.jsx` | Mock exam definitions (`buildTests`) |
| `scripts/convert.py` | Source pipeline from manuals → `public/data/*` |

## UX engineering

- **ErrorBoundary** (`main.jsx`) — isolates render crashes.
- **React.lazy** — `Manuals` and `Tests` code-split with `ViewSkeleton`.
- **ContextualHelp** — compact “?” panels on Dashboard, Tests, Reader.
- **Mobile “More” sheet** — second tap to Manuals, Flashcards, Planner, About.

## Deploy

`npm run build` → `scripts/deploy.py` (rsync-style upload to `/srv/apea/study` when `DEDI_PW` is set).
