/**
 * Guided workbook content.
 *
 * The PDF extractor is useful for source tables, but a workbook needs an
 * instructional sequence. These prompts deliberately move from foundation to
 * classification to clinical application. Hand-authored chapter blueprints can
 * override the generic sequence when the source deserves a tighter treatment.
 */

const HEMATOLOGY = {
  title: 'RBC indices, anemia patterns & CBC interpretation',
  subtitle: 'Build the pattern first, then use it to make a clinical decision.',
  objectives: [
    'Interpret MCV, MCHC, RDW, reticulocytes, ferritin, serum iron, and TIBC.',
    'Separate iron deficiency, thalassemia trait, chronic inflammation, and B12/folate deficiency.',
    'Recognize when anemia, thrombocytopenia, or an abnormal differential needs urgent follow-up.',
  ],
  concepts: [
    {
      prompt: 'Which three CBC measures can establish that a patient is anemic?',
      answer: 'A low hemoglobin, hematocrit, or RBC count can establish anemia. Interpret the result against the laboratory range and the patient’s age, sex, pregnancy status, symptoms, and baseline.',
    },
    {
      prompt: 'What does MCV measure, and how does it classify anemia?',
      answer: 'MCV is the average RBC volume: microcytic below 80 fL, normocytic about 80–100 fL, and macrocytic above 100 fL. Laboratory reference ranges vary slightly.',
    },
    {
      prompt: 'What does RDW add to the interpretation of MCV?',
      answer: 'RDW describes variation in RBC size. A high RDW suggests mixed or evolving cell populations and commonly supports iron deficiency; a normal RDW with marked microcytosis raises suspicion for thalassemia trait.',
    },
    {
      prompt: 'What question does the reticulocyte count answer in an anemic patient?',
      answer: 'It asks whether the marrow is responding. An appropriately high reticulocyte response suggests blood loss or hemolysis; a low or inappropriately normal response suggests impaired production.',
    },
    {
      prompt: 'What iron-study pattern supports iron-deficiency anemia?',
      answer: 'Low ferritin and serum iron with elevated TIBC/transferrin. Ferritin may be falsely normal or high during inflammation, so interpret it in clinical context.',
    },
    {
      prompt: 'Why must vitamin B12 deficiency be considered before treating folate deficiency alone?',
      answer: 'Folate can improve the anemia while B12-related neurologic injury continues. Check for B12 deficiency when macrocytosis or neurologic symptoms are present.',
    },
  ],
  matrix: {
    title: 'Classify the anemia',
    headers: ['Pattern', 'MCV / RDW', 'Iron studies or clues', 'FNP next step'],
    rows: [
      ['Iron deficiency', 'Microcytic; RDW often high', 'Low ferritin, low Fe, high TIBC', 'Find and treat the source of blood loss; replace iron'],
      ['Thalassemia trait', 'Marked microcytosis; RDW often normal', 'Iron studies usually normal; target cells may appear', 'Hemoglobin electrophoresis; avoid empiric iron unless deficient'],
      ['Chronic inflammation', 'Usually normocytic; may become microcytic', 'Low Fe, low/normal TIBC, normal/high ferritin', 'Treat the underlying disease; assess CKD/inflammation'],
      ['B12 deficiency', 'Macrocytic', 'Neuropathy, glossitis; low B12 ± high MMA', 'Identify cause and replace B12; do not delay with neurologic symptoms'],
      ['Folate deficiency', 'Macrocytic', 'No characteristic neuropathy; low folate', 'Exclude B12 deficiency, then replace folate and address cause'],
    ],
  },
  patternChecks: [
    {
      label: 'Pattern A',
      data: 'Hgb 10.5 · MCV 76 · RDW 18.6 · ferritin low · TIBC high',
      prompt: 'Name the most likely anemia and the priority etiologic evaluation.',
      answer: 'Iron-deficiency anemia. Identify the bleeding source: menstrual history when relevant and GI evaluation when age/risk/history warrants it.',
    },
    {
      label: 'Pattern B',
      data: 'Age 17 · Hgb 9.5 · MCV 72 · RDW normal · iron panel normal',
      prompt: 'What diagnosis moves up the differential, and what test comes next?',
      answer: 'Thalassemia trait; order hemoglobin electrophoresis. Do not prescribe iron unless iron deficiency is demonstrated.',
    },
    {
      label: 'Pattern C',
      data: 'Older adult · Hgb 10.3 · MCV 103 · paresthesias and gait change',
      prompt: 'What deficiency is most concerning, and what should be checked?',
      answer: 'Vitamin B12 deficiency. Check serum B12 and, when the result is borderline or suspicion remains high, methylmalonic acid.',
    },
    {
      label: 'Red flag',
      data: 'Fatigue · bruising · anemia · thrombocytopenia · circulating blasts',
      prompt: 'What is the safest disposition?',
      answer: 'Urgent hematology/emergency evaluation for possible acute leukemia or marrow failure; this is not routine outpatient watchful waiting.',
    },
  ],
  pearls: [
    'Anemia is a finding, not the final diagnosis—identify the cause.',
    'Microcytosis with normal iron studies is not automatically iron deficiency.',
    'Neurologic symptoms distinguish B12 deficiency from an uncomplicated folate deficiency pattern.',
    'New iron deficiency in an older adult requires evaluation for occult blood loss.',
  ],
}

const BLUEPRINTS = { hematology: HEMATOLOGY }

function clean(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function usableTables(chapter) {
  const tables = []
  chapter.sections.forEach(section => (section.blocks || []).forEach(block => {
    if (block.type !== 'table' || !block.headers?.length || !block.rows?.length) return
    if (/question\s*#|patient normal range/i.test(block.headers.join(' '))) return
    if (block.headers.some(h => clean(h).length > 70)) return
    tables.push({ title: section.title, headers: block.headers, rows: block.rows })
  }))
  return tables
}

/**
 * Every chapter gets the same professional learning arc. Chapters with a curated
 * blueprint replace the generated concept/matrix sections, while board questions
 * still come from the quality-controlled question bank.
 */
export function guidedWorkbookFor(chapter) {
  const curated = BLUEPRINTS[chapter.id]
  const tables = usableTables(chapter)
  if (curated) return { ...curated, tables }

  const title = chapter.shortTitle || chapter.title
  const sectionNames = chapter.sections
    .map(section => clean(section.title))
    .filter((name, index, all) => name && name.length < 65 && all.indexOf(name) === index)
    .slice(0, 4)

  return {
    title: `${title}: clinical reasoning workbook`,
    subtitle: 'Move from key findings to diagnosis, treatment, and follow-up.',
    objectives: [
      `Recognize the common presentations and red flags in ${title}.`,
      'Select the most appropriate diagnostic test or clinical next step.',
      'Choose first-line management and know when referral is required.',
    ],
    concepts: sectionNames.map(name => ({
      prompt: `For ${name}, what presentation, diagnostic clue, and first-line action should an FNP know?`,
      answer: `Use the source table and board questions below to build a concise presentation → diagnosis → management summary for ${name}.`,
    })),
    matrix: tables[0] || null,
    patternChecks: [],
    pearls: [],
    tables,
  }
}

