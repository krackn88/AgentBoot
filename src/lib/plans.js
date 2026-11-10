/** Planned tiers — beta stays fully open (see config BETA_OPEN). */
export const PLANS = {
  free: {
    id: 'free',
    name: 'Open beta',
    priceLabel: '$0 while testing',
    tagline: 'Full access during beta — help us polish before launch.',
    includes: [
      'Every chapter, manual, and workbook',
      'Question bank & flashcards',
      'Progress saved on your device',
    ],
  },
  pro: {
    id: 'pro',
    name: 'Pro (planned)',
    priceLabel: 'TBD at launch',
    tagline: 'One structured platform instead of 1.2 GB of PDFs and scattered notes.',
    includes: [
      'Every graded MCQ with Answer Key rationales',
      '22 searchable course manuals + original PDFs',
      'Timed AANP/ANCC mock exams & readiness score',
      '12-week guided path + personalized weak-area radar',
      'Clinical pearls, workbooks (1,700+ drills), print packets',
      'Readiness report export & progress backup',
      'Hosted updates for the APEA 2026 cohort',
    ],
  },
}

export const COMPARE_ROWS = [
  { feature: 'All 21 guide chapters + search', pdf: 'Scattered PDFs', platform: true },
  { feature: '22 full course manuals', pdf: '~1.2 GB download', platform: true },
  { feature: 'Graded MCQs + rationales', pdf: 'Manual answer key only', platform: true },
  { feature: 'Mock exams (timed)', pdf: 'Self-made', platform: 'AANP · ANCC · manual banks' },
  { feature: 'Weak-area tracking', pdf: '—', platform: true },
  { feature: 'Flashcards + spaced review', pdf: '—', platform: true },
  { feature: 'Board readiness score', pdf: '—', platform: true },
  { feature: '12-week study path', pdf: '—', platform: true },
  { feature: 'Printable readiness report', pdf: '—', platform: true },
]
