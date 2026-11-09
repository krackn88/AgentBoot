import { PLATFORM } from './config'
import { streakOf } from './store'

export function weakChapters(guide, store) {
  const qChapter = {}
  guide.chapters.forEach(c => c.questions.forEach(q => { qChapter[q.id] = c }))
  const by = {}
  Object.entries(store.answers || {}).forEach(([qid, a]) => {
    const c = qChapter[qid]
    if (!c) return
    by[c.id] = by[c.id] || { chapter: c, t: 0, ok: 0 }
    by[c.id].t++
    if (a.correct) by[c.id].ok++
  })
  return Object.values(by)
    .map(r => ({ title: r.chapter.shortTitle, number: r.chapter.number, pct: Math.round(r.ok / r.t * 100), tried: r.t }))
    .sort((a, b) => a.pct - b.pct)
    .slice(0, 8)
}

export function mockScores(store) {
  return (store.quizHistory || [])
    .filter(h => h.testId && !String(h.testId).startsWith('ch-'))
    .map(h => ({
      title: h.title || h.testId,
      pct: h.graded ? Math.round((h.correct / h.graded) * 100) : null,
      date: h.date,
      testId: h.testId,
    }))
    .slice(-6)
}

export function buildReadinessReport(ctx) {
  const { guide, store, readiness, doneCh, totalCh, answered, totalQ, accuracy, mastered, streak } = ctx
  return {
    generatedAt: new Date().toISOString(),
    platform: PLATFORM.name,
    examDate: store.examDate || null,
    readinessPercent: readiness,
    chapters: { completed: doneCh, total: totalCh, percent: Math.round((doneCh / totalCh) * 100) },
    questions: { answered, total: totalQ, accuracyPercent: accuracy },
    flashcards: { mastered },
    streakDays: streak ?? streakOf(store.studyDates || []),
    mockExams: mockScores(store),
    weakChapters: weakChapters(guide, store),
    studyDays: (store.studyDates || []).length,
  }
}

export function downloadReadinessJson(report) {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `apea-readiness-${report.generatedAt.slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

export function openPrintableReadinessReport(report) {
  const weak = report.weakChapters.length
    ? report.weakChapters.map(w => `<tr><td>${esc(w.number)}. ${esc(w.title)}</td><td>${w.tried}</td><td>${w.pct}%</td></tr>`).join('')
    : '<tr><td colspan="3">Answer chapter quizzes to populate weak areas.</td></tr>'
  const mocks = report.mockExams.length
    ? report.mockExams.map(m => `<tr><td>${esc(m.title)}</td><td>${m.date}</td><td>${m.pct != null ? m.pct + '%' : '—'}</td></tr>`).join('')
    : '<tr><td colspan="3">No timed mocks yet — run one under Mock exams.</td></tr>'
  const examLine = report.examDate
    ? `<p><strong>Target exam:</strong> ${esc(new Date(report.examDate + 'T12:00:00').toLocaleDateString())}</p>`
    : ''

  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Readiness Report — ${esc(PLATFORM.name)}</title>
<style>
body{font-family:system-ui,sans-serif;max-width:720px;margin:32px auto;padding:0 20px;color:#0c1a2e;line-height:1.5}
h1{font-size:26px;margin:0 0 4px}h2{font-size:16px;margin:24px 0 8px;text-transform:uppercase;letter-spacing:.06em;color:#71809a}
.stat{font-size:36px;font-weight:800;margin:8px 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:16px 0}
.box{border:1px solid #e2e8f0;border-radius:12px;padding:14px}
table{width:100%;border-collapse:collapse;font-size:14px;margin:8px 0}
th,td{border:1px solid #e2e8f0;padding:8px;text-align:left}
th{background:#eef3f9}
.footer{margin-top:32px;font-size:12px;color:#71809a;border-top:1px solid #e2e8f0;padding-top:12px}
@media print{body{margin:16px}}
</style></head><body>
<p style="font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:#0e7c6b;font-weight:800;margin:0">Board prep summary</p>
<h1>${esc(PLATFORM.name)}</h1>
<p>Generated ${esc(new Date(report.generatedAt).toLocaleString())}</p>
${examLine}
<div class="box"><p style="margin:0;font-size:12px;color:#71809a;text-transform:uppercase;font-weight:800">Composite readiness</p>
<p class="stat">${report.readinessPercent}%</p>
<p style="margin:0">Chapters ${report.chapters.completed}/${report.chapters.total} · ${report.questions.answered} questions · ${report.streakDays}-day streak</p></div>
<div class="grid">
<div class="box"><strong>Question accuracy</strong><p class="stat" style="font-size:28px">${report.questions.accuracyPercent}%</p><p style="margin:0;font-size:13px">${report.questions.answered} of ${report.questions.total} tried</p></div>
<div class="box"><strong>Flashcard mastery</strong><p class="stat" style="font-size:28px">${report.flashcards.mastered}</p><p style="margin:0;font-size:13px">${report.studyDays} study days logged</p></div>
</div>
<h2>Recent mock exams</h2><table><thead><tr><th>Exam</th><th>Date</th><th>Score</th></tr></thead><tbody>${mocks}</tbody></table>
<h2>Focus next (lowest accuracy)</h2><table><thead><tr><th>Chapter</th><th>Attempts</th><th>Accuracy</th></tr></thead><tbody>${weak}</tbody></table>
<p class="footer">Personal study record from ${esc(PLATFORM.name)} — not an official APEA or board credential. Built from official APEA 2026 course manuals hosted for this cohort.</p>
</body></html>`
  const w = window.open('', '_blank', 'noopener')
  if (!w) {
    alert('Allow pop-ups to open the printable report, or use Download JSON.')
    return
  }
  w.document.write(html)
  w.document.close()
  w.focus()
  setTimeout(() => w.print(), 400)
}
