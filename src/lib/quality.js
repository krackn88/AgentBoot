/**
 * Applies the quality overlay produced by scripts/quality_pass.py:
 *  - cleans answer options that swallowed slide headers during PDF extraction
 *  - flags manual-slide items that duplicate a study-guide stem, so mixed pools
 *    don't show the same question twice
 *  - attaches a manual section anchor so any answer can be verified in context
 */

export const EMPTY_OVERLAY = { options: {}, duplicates: {}, anchors: {}, meta: {} }

function withOptionFix(q, overlay) {
  const fix = overlay.options?.[q.id]
  return fix?.options ? { ...q, options: fix.options } : q
}

function withAnchor(q, overlay) {
  const anchor = overlay.anchors?.[q.id]
  return anchor ? { ...q, anchor } : q
}

export function applyGuideQuality(guide, overlay, rationales) {
  if (!guide) return guide
  const hasQuality = overlay?.meta
  const hasRationales = rationales?.questions && Object.keys(rationales.questions).length
  if (!hasQuality && !hasRationales) return guide

  return {
    ...guide,
    chapters: guide.chapters.map(ch => ({
      ...ch,
      questions: ch.questions.map(q => {
        let next = hasQuality ? withAnchor(withOptionFix(q, overlay), overlay) : q
        const upgrade = rationales?.questions?.[q.id]
        if (upgrade?.explanation) {
          next = { ...next, explanation: upgrade.explanation, rationaleSource: 'manual' }
        }
        return next
      }),
    })),
  }
}

export function applyManualQuality(manualBank, overlay) {
  if (!overlay?.meta || !manualBank) return manualBank
  return {
    ...manualBank,
    questions: (manualBank.questions || []).map(q => {
      const next = withAnchor(withOptionFix(q, overlay), overlay)
      const dup = overlay.duplicates?.[q.id]
      return dup ? { ...next, duplicateOf: dup.dupOf } : next
    }),
  }
}

/** True when a question is gradable and not a duplicate of another bank item. */
export function isUniqueGraded(q) {
  return q.correctIndex != null && (q.options?.length ?? 0) >= 2 && !q.duplicateOf
}

export function uniqueGraded(questions) {
  return questions.filter(isUniqueGraded)
}
