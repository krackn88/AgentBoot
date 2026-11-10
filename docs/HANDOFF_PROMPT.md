# Handoff prompt — APEA 2026 FNP Study Hub

Copy everything below the line into a new chat with the assistant you want to help.

---

## What this project is

A single-page React study site for one user: a nurse with 15 years of RN experience finishing her FNP/AGNP certification. It hosts the APEA 2026 course materials she already owns — 21 chapters, 22 full course manuals, ~527 graded MCQs, mock exams, spaced repetition, and printable study packets. She is **skeptical and experienced**; if the content is vague or wrong she closes the tab and does not come back. The bar is "would a 15-year RN trust this enough to study from it," not "does it render."

**Live site:** https://giftr.duckdns.org/apea/study/

## Repository and how to connect

- **Repo:** `krackn88/AgentBoot` (GitHub, private)
- **Working branch:** `cursor/professional-bank-coverage-dc89` — this is where all current work lives
- **Base branch:** `main`
- **App lives at the repo root** (not in a subfolder). `index.html`, `src/`, `public/`, `scripts/` are top level.
- The app is served under the base path `/apea/study/` — `vite.config.js` sets `base: '/apea/study/'`. All asset and data fetches must respect `import.meta.env.BASE_URL`.

### Getting a working copy

```bash
git clone https://github.com/krackn88/AgentBoot.git
cd AgentBoot
git checkout cursor/professional-bank-coverage-dc89
npm install
npm run dev          # http://localhost:5173/apea/study/
```

Requires Node 20+ (developed on Node 22) and Python 3.12 for the content scripts.

### Deploying (only if asked)

Deployment is **not** part of normal work. The site is served from a Hetzner box at `159.69.76.189` (`/srv/apea/study`). Script: `scripts/deploy.py`, requires the `DEDI_PW` environment variable. **Do not deploy unless explicitly asked.** `npm run build` is the normal verification step.

## Stack

- React 19 + Vite 6, no router library (hash routing: `#/dashboard`, `#/library`, `#/reader/<chapterId>`, `#/manuals`, `#/quiz`, `#/flashcards`, `#/tests`, `#/workbooks`, `#/quickref`, `#/planner`, `#/about`)
- `lucide-react` icons, hand-written CSS in `src/styles.css` (no Tailwind)
- State: `localStorage` only (`apea-hub-v2`), no backend, no auth, no payments
- PWA: `public/manifest.webmanifest`, `public/sw.js`

## Data layout (`public/data/`)

All content is static JSON fetched at runtime; nothing is hardcoded in components.

| File | Contents |
|---|---|
| `guide.json` | 21 chapters: sections, blocks (p/table/list), questions, quick-reference tables |
| `modules/<chapterId>.json` | per-chapter `reference.tables` (rebuilt by Docling) and `reference.fragments` |
| `manual-questions.json` | 262 slide MCQs, each with a `grading` field |
| `question-quality.json` | overlay: cleaned options, duplicate flags, source anchors |
| `rationale-upgrades.json` | extended rationales built from manual text |
| `professional-questions.json` | 37 hand-written items for chapters 20–21 |
| `pearls-clean.json` | 89 reviewed pearls (30 rules, 27 rationales, 32 instructor TIPs) |
| `pdf-lists.json` | ~548 recall drills derived from PDF bullet lists |
| `docling/<chapterId>.json` | Docling extraction: tables, markdown, tips, questions |
| `search-chunks/` | dictionary-encoded search index (`manifest.json`, `core.json`, `manual.json`) |
| `manuals/*.md` | full text of the 22 course manuals |

## Content pipeline

`npm run content:build` regenerates all derived data. Steps in order: `enrich → extract:questions → sync:manual-answers → bulk:manual-answers → tables → depth → quality → rationales → search-index → pearls → pdf:merge → pdf:drills`.

PDF extraction (needs the 1.2 GB of PDFs, fetched from the server):
```bash
DEDI_PW=... npm run pdf:fetch     # downloads to /tmp/pdfs
npm run pdf:docling                # Docling layout model + TableFormer
npm run pdf:merge                  # merge Docling tables into modules
```

## Testing (this is the important part)

```bash
npm run smoke     # renders every route in jsdom + content assertions
npm run verify    # smoke + build
```

`scripts/smoke_render.mjs` renders **every route** against the real data files and asserts: no out-of-range answer indices, no duplicate or over-long options, every question has a rationale, every chapter has non-empty tables, the planner covers all 21 chapters at every runway length, pearls and drills carry no slide furniture or copyright lines, and a fresh spaced-repetition account gets a small first session.

**Known blind spot:** React server rendering emits `<details>` with **no children**, so anything inside a disclosure widget is invisible to the smoke test. That is how a crash shipped to production once. Content inside `<details>` must either be always-rendered or explicitly tested.

## The bug class to watch for

Three separate screens shipped the same defect: **a bare table cell presented as a question.**

- A drill read `prompt: "Itch"` / `hint: "HIVES?"` / `answer: "Intense"` — the underlying table row was correct (`Hives | Itch | Intense`), but the question was stripped of all framing.
- A flashcard front was `"Live vaccines"` with the rule on the back.
- An intermediate "fix" produced `"For Live vaccines, what is the Must-know number or rule?"` — a generic column header leaking into the question.

The root cause is that most second columns are *descriptions of the column* (`Must-know number or rule`, `Description`, `Notes`, `Value`) rather than properties of the subject.

`src/lib/drills.js` is the single place that turns a table into a question. `src/lib/readability.js` defines what "reads as a question" means and can audit a batch of cards. **Any new card or drill surface must be run through both.**

## Current known gaps (do not pretend these are fixed)

1. **79 manual answers are unverified.** They were keyed by text-scoring inference. The source PDFs contain **no answer key**, which is why they cannot be confirmed. They are excluded from graded exams (`src/lib/examPool.js`) but still appear in practice.
2. **Pearl cards and high-yield cards can ask the same question** ("What is the key point about live vaccines?") because both derive from the same rule table.
3. **Question-card answers sometimes repeat themselves** (`"Clindamycin — Clindamycin carries the highest…"`).
4. **Some question stems are truncated fragments** (`"Most likely to cause C. difficile?"`).
5. **`pearls-clean.json` uses lowercase acronyms** in prompts (`aom`, `peds pneumonia`) when they should be `AOM`.
6. **No visual/layout testing** — everything above is data and render-assertion level. Mobile layout has only been checked by eye in screenshots.

## What is wanted next

Polish and depth, in this order:

1. Make **every** card and drill read as a real question — no bare cells, no header leakage, no duplicate prompts across decks, no truncated stems.
2. Fill out thin chapters. Dermatology, Pregnancy, and EENT have the least content.
3. Make the visual design feel finished on a phone (the primary device).

## Conventions

- Voice: plain, clinical, no marketing. Do not invent clinical content — if it is not in the source, say so.
- Prefer deleting a feature over shipping something vague.
- Every user-facing count must be computed from data (`src/lib/contentStats.js`), never hardcoded.
- Commit in small logical commits with a message explaining the *why*. Do not amend or force-push.
- If a content claim cannot be verified, state that plainly rather than smoothing it over.
