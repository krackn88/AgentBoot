/**
 * Turn reference tables into questions a clinician would actually ask.
 *
 * Three bad card and drill shapes came out of earlier versions of this file:
 *
 *   front: "Live vaccines"                                   (a bare cell)
 *   front: "For Live vaccines, what is the Must-know number or rule?"   (header leaked in)
 *   front: "In Must-know number or rule, what is the Vaccine timing like?" (backwards)
 *
 * The cause was treating every column header as a property name. In these slides
 * most second columns are *descriptions of the column* ("Must-know number or rule",
 * "Description", "Notes", "Value"), not properties of the subject. When the header
 * is generic, the subject is the only thing worth asking about, and the prompt
 * should simply name it and ask for the rule.
 */

// Column headers that describe the contents of a column rather than a property.
const GENERIC_HEADER = /^(must[- ]know.*|key (points?|rules?|facts?|takeaways?)|description|details?|notes?|notes\/pearls?|value|values|answer|answers|comment|comments|considerations?|pearls?|guidance|summary|explanation|example|examples|content|information|data|other|misc)\s*:?\s*$/i

// Headers that name a property we can ask about directly.
const PROPERTY_HEADER = /^(look|appearance|itch|course|timing|onset|duration|dose|dosing|frequency|route|mechanism|monitor\w*|side effects?|adverse\w*|contraindicat\w*|causes?|symptoms?|signs?|findings?|diagnosis|criteria|screening|vaccine|schedule|treatment|management|first[- ]line|alternative|indications?|risk factors?|complications?|examples?|drugs?|coverage|spectrum|generation|class|type|stage|grade|level)\s*:?\s*$/i

// A row label that is really a data value cannot anchor a question.
const VALUE_LIKE_LABEL = /^(\d+|NOT\s+\w+|—|-)$/i

const STOP_ACRONYM = /^[A-Z]{2,6}$/

function clean(s) {
  return String(s ?? '')
    .replace(/\s+/g, ' ')
    .trim()
}

/** "aom" -> "AOM", "live vaccines" -> "live vaccines" */
function phrase(subject) {
  return topicPhrase(subject)
}

/** Title-case a subject only when it is a plain phrase, preserving acronyms. */
function asSubject(subject) {
  return clean(subject)
    .split(/\s+/)
    .map(w => (STOP_ACRONYM.test(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(' ')
}

function isGeneric(header) {
  return !clean(header) || GENERIC_HEADER.test(clean(header))
}

function isProperty(header) {
  return PROPERTY_HEADER.test(clean(header))
}

/** Does this table support at least one real question? */
export function tableIsDrillable(table) {
  const headers = (table?.headers || []).map(clean)
  const rows = table?.rows || []
  if (headers.length < 2 || rows.length < 2) return false
  const usable = rows.filter(r => r && clean(r[0]) && clean(r[0]).length <= 90)
  if (usable.length < 2) return false
  // We need either a generic "description" column (ask about the row subject) or a
  // real property column alongside a usable subject column.
  const hasGeneric = headers.slice(1).some(isGeneric)
  const hasProperty = headers.slice(1).some(isProperty)
  return hasGeneric || hasProperty
}

/**
 * Build the question text.
 * @param {string} subject row label
 * @param {string} header column header
 * @param {string} value cell
 * @param {string} labelHeader header of the first column, if it names a property
 */
function buildPrompt(subject, header, labelHeader) {
  const sub = clean(subject)
  const hdr = clean(header)
  if (!sub) return ''

  // 1. The row label is a property ("Itch") and the column names the subject
  //    ("Hives") -> "In hives, what is the itch like?"
  if (isProperty(labelHeader) || (!clean(labelHeader) && isProperty(sub))) {
    return `In ${phrase(hdr)}, what is the ${phrase(sub)}?`
  }

  // 2. The column header is generic -> just ask about the row subject.
  if (isGeneric(hdr)) {
    return `What is the key point about ${phrase(sub)}?`
  }

  // 3. The column header is a real property -> "In <subject>, what is the <property>?"
  if (isProperty(hdr)) {
    return `In ${phrase(sub)}, what is the ${phrase(hdr)}?`
  }

  // 4. Otherwise the header is a plain label -> "For <subject>, what is the <header>?"
  if (hdr.length <= 40) {
    return `For ${phrase(sub)}, what is the ${phrase(hdr)}?`
  }
  return `What is the key point about ${phrase(sub)}?`
}

/**
 * Turn one table into card/drill rows.
 * Each row: { id, prompt, answer, subject, column, table }
 */
export function drillsFromTable(table, { section = '', tableKey = 't' } = {}) {
  const headers = (table?.headers || []).map(clean)
  const rows = table?.rows || []
  if (!tableIsDrillable(table)) return []

  const labelHeader = headers[0] || ''
  const out = []

  rows.forEach((row, ri) => {
    const subject = clean(row?.[0])
    if (!subject || subject.length > 90) return
    if (VALUE_LIKE_LABEL.test(subject)) return

    headers.forEach((header, ci) => {
      if (ci === 0) return
      const value = clean(row?.[ci])
      if (!value || value === '—' || value === '-' || value.length > 260) return

      const prompt = buildPrompt(subject, header, labelHeader)
      if (!prompt) return

      out.push({
        id: `${tableKey}-r${ri}-c${ci}`,
        prompt,
        answer: value,
        subject: asSubject(subject),
        column: header,
        section,
        table,
      })
    })
  })

  // De-duplicate identical prompts (a subject can appear in several rows).
  const seen = new Set()
  return out.filter(d => {
    const k = d.prompt.toLowerCase()
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
}


/** Lowercase a topic for use mid-sentence but keep acronyms ("AOM", "GERD", "CKD"). */
export function topicPhrase(topic) {
  return clean(topic)
    .split(/\s+/)
    .map(w => (/^[A-Z][A-Z0-9/\-]{1,7}$/.test(w) ? w : /[A-Z]/.test(w) && /\d/.test(w) ? w : /^a1c$/i.test(w) ? 'A1c' : w.toLowerCase()))
    .join(' ')
}

/** "AOM: Amoxicillin 80-90 mg/kg..." -> { topic: "AOM", detail: "Amoxicillin ..." } */
export function splitTopic(text) {
  const t = clean(text)
  const i = t.indexOf(':')
  if (i >= 2 && i < 60) return { topic: t.slice(0, i).trim(), detail: t.slice(i + 1).trim() }
  return { topic: '', detail: t }
}

/**
 * Collapse "Answer — explanation" when the explanation just restates the answer
 * ("Clindamycin — Clindamycin carries the highest C. difficile risk.").
 */
export function answerWithWhy(answer, explanation) {
  const a = clean(answer).replace(/[.\s]+$/, '')
  const e = clean(explanation)
  if (!e) return a
  const norm = x => x.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
  const na = norm(a)
  const ne = norm(e)
  if (!na) return e
  // explanation begins with the answer -> the explanation already says it
  if (ne.startsWith(na) || ne.includes(na) && na.split(' ').length >= 2 && na.length > 12) return e
  const words = na.split(' ').filter(w => w.length >= 4)
  const ew = new Set(ne.split(' '))
  if (words.length >= 3 && words.filter(w => ew.has(w)).length / words.length >= 0.8) return e
  return /["”')]$/.test(a) ? `${a} — ${e}` : `${a}. ${e}`
}

const UNIT = '%|mg/kg/day|mg/kg|mg/dL|mg|mcg|g/dL|weeks?|months?|years?|days?|hours?|minutes?|units?|mmHg|mm|cm|kg|lbs?'
const CLOZE_NUMBER = new RegExp(`(?<![A-Za-z0-9\\-])(?:[<>≥≤]=?\\s?\\d+(?:[.\\-–/]\\d+)?(?:\\s?(?:${UNIT}))?|\\d+(?:[.\\-–/]\\d+)?\\s?(?:${UNIT})\\b)`)
const CLOZE_ACRONYM = /\b[A-Z][A-Za-z]{0,3}[A-Z0-9][A-Za-z0-9-]*\b/
const CLOZE_BARE_NUMBER = /(?<![A-Za-z0-9-])\d+(?:[.\-–/]\d+)?\b/

/**
 * Turn a one-sentence pearl into a fill-in-the-blank, hiding the fact worth
 * remembering (a number, dose, or named test/drug). Returns null when the sentence
 * has nothing specific to hide — a card that asks "finish this sentence" with no
 * anchor is not testing anything, so those pearls are left out of the card decks.
 */
export function clozeFrom(text) {
  const t = clean(text)
  if (t.split(/\s+/).length < 6 || t.length > 220) return null
  const m = t.match(CLOZE_NUMBER) || t.match(CLOZE_ACRONYM) || t.match(CLOZE_BARE_NUMBER)
  if (!m) return null
  const target = m[0].trim()
  const blanked = t.slice(0, m.index) + '_____' + t.slice(m.index + m[0].length)
  const sentence = blanked.replace(/[!\s]+$/, '').replace(/([^.?])$/, '$1.')
  return { prompt: `Fill in the blank: ${sentence}`, answer: target, full: t }
}

const SENTENCE_TOPIC = /\b(is|are|was|were|mean|means|suggests?|indicates?|if|when|persists?|fails?|despite|after|with|without)\b/i

/** Prompt for a "Topic: detail" pearl. Sentence-like topics become "key point when…". */
export function pearlPrompt(topic) {
  const t = topicPhrase(topic)
  if (!t) return ''
  if (t.split(' ').length >= 5 || SENTENCE_TOPIC.test(t)) return `What is the key point when ${t.replace(/^(if|when)\s+/i, '')}?`
  return `What should you know about ${t}?`
}
