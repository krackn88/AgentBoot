// Original APEA 2026 course-manual PDFs already hosted on the dedi under /apea/2026-fnp-manuals/pdf/
export const PDFS = [
  '01-introduction-course-manual.pdf','02-exam-prep-course-manual.pdf','03-antibiotics-course-manual.pdf',
  '04-pulmonary-disorders-course-manual.pdf','05-hematology-course-manual.pdf','06-neurologic-disorders-course-manual.pdf',
  '07-mental-health-course-manual.pdf','08-gastrointestinal-disorders-course-manual.pdf','09-urology-and-sti-course-manual.pdf',
  '10-cardiovascular-disorders-course-manual.pdf','11-endocrine-disorders-course-manual.pdf','12-womens-health-course-manual.pdf',
  '13-mens-health-course-manual.pdf','14-orthopedic-disorders-course-manual.pdf','15-dermatological-disorders-course-manual.pdf',
  '16-eye-ear-nose-throat-course-manual.pdf','17-care-of-aging-adult-course-manual.pdf','18-pregnancy-primary-care-course-manual.pdf',
  '19-pediatrics-course-manual.pdf','20-pediatric-growth-development-course-manual.pdf','21-entry-into-practice-course-manual.pdf',
  '22-professional-issues-course-manual.pdf',
]
export const pdfUrlForChapter = (chapter) => `/apea/2026-fnp-manuals/pdf/${PDFS[chapter.number]}` // guide ch.1 = PDF 02, etc.
export const introPdfUrl = `/apea/2026-fnp-manuals/pdf/${PDFS[0]}`
