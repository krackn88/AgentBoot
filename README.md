# APEA 2026 FNP Study Hub

All-in-one board-prep hub at https://giftr.duckdns.org/apea/study/ — built from
`APEA_2026_FNP_Complete_Study_Guide_a015.docx` (21 chapters, 224 tables, 278 practice
questions) plus the original course-manual PDFs hosted on the dedi.

## Features
- **Dashboard** — board-readiness score (chapters 40% · question accuracy 30% · flashcard mastery 30%), streak, continue-studying
- **Study Guide** — all 21 chapters in manual order, searchable, section TOC, bookmarks, mark-complete, original PDF per chapter
- **Full Manual Library** — all 22 original manuals as complete searchable text (914K source bytes) and embedded page-accurate originals (1.2 GB), with cross-corpus search
- **Practice & Exam Simulator** — per-chapter practice with instant Answer-Key rationales, mixed quizzes, missed-question deck, 50-question / 60-min timed exam at AANP pace (72s/q) with flagging + navigator, per-chapter results breakdown
- **Flashcards** — Leitner-box decks built from real content: High-Yield Quick Reference, Labs to Commit to Memory, question cards, personal missed deck
- **High-Yield Quick Reference**, **Study Planner** (exam-date → day-by-day plan weighted by chapter size), **Pro pricing + waitlist**
- Progress persists in `localStorage` (`apea-hub-v2`)

## Develop / rebuild content
```bash
npm install
npm run convert -- /path/to/APEA_2026_FNP_Complete_Study_Guide_a015.docx  # regenerates public/data/guide.json (fetched at runtime, keeps the JS bundle small)
npm run sync:manuals # refreshes the complete 22-manual text corpus + metadata from the dedi
npm run dev        # local dev
npm run build      # -> dist/ (base /apea/study/)
```

## Deploy (dedi: 159.69.76.189, Caddy serves /srv/apea/study)
```bash
npm run build
DEDI_PW='...' python3 scripts/deploy.py   # backs up old site to /srv/apea/study-backup-<ts>, then swaps in dist/
```
Original PDFs stay untouched at `/srv/apea/2026-fnp-manuals/pdf/` and are linked from every chapter.
