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
  conceptCards: [
    { term: 'MCV', measures: 'Mean corpuscular volume — average RBC size', normal: '80–100 fL', clue: '<80 microcytic · >100 macrocytic. The first branch point of every anemia.' },
    { term: 'MCHC', measures: 'Hemoglobin concentration inside the RBC', normal: '32–36 g/dL', clue: 'Low = hypochromic (pale cells) — think iron deficiency or thalassemia.' },
    { term: 'RDW', measures: 'Variation in RBC size', normal: '~12–15%', clue: 'High early in iron deficiency; often normal in thalassemia trait.' },
    { term: 'Reticulocyte', measures: 'Immature RBCs leaving the marrow', normal: '0.5–2.5%', clue: 'High = marrow responding (loss/hemolysis). Low in anemia = production problem.' },
    { term: 'Ferritin', measures: 'Iron stores', normal: 'Low = iron deficiency', clue: 'Also an acute-phase reactant — inflammation can mask deficiency.' },
    { term: 'TIBC', measures: 'Transferrin binding capacity', normal: 'High when iron is scarce', clue: 'IDA pattern: ferritin \u2193, serum Fe \u2193, TIBC \u2191.' },
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


const CARDIOLOGY = {
  title: 'Hypertension, heart failure & the cardiovascular exam',
  subtitle: 'Decode the numbers · classify the syndrome · protect the organs.',
  objectives: [
    'Stage hypertension and choose first-line therapy by compelling indication.',
    'Separate HFrEF from HFpEF and name guideline-directed therapy.',
    'Use murmur timing, radiation, and maneuvers to narrow the lesion.',
  ],
  conceptCards: [
    { term: 'Office BP', measures: 'Seated, correct cuff, rested 5 min', normal: 'Confirm elevated readings', clue: 'Out-of-office (home/ABPM) confirms true HTN and finds white-coat effect.' },
    { term: 'Stage 2 HTN', measures: 'ACC/AHA staging', normal: '\u2265140/90', clue: 'Usually needs two first-line drugs from different classes.' },
    { term: 'BNP / NT-proBNP', measures: 'Myocardial wall stress', normal: 'Low makes HF less likely', clue: 'Higher with age, AF, CKD; lower in obesity — interpret in context.' },
    { term: 'CHA\u2082DS\u2082-VASc', measures: 'Stroke risk in AF', normal: 'Guides anticoagulation', clue: 'Anticoagulate at score \u22652 (men) / \u22653 (women); consider at 1/2.' },
  ],
  concepts: [
    { prompt: 'Which four drug classes are first-line for uncomplicated hypertension?', answer: 'Thiazide-type diuretic, ACE inhibitor or ARB, and dihydropyridine calcium channel blocker (amlodipine). Never combine an ACE inhibitor with an ARB.' },
    { prompt: 'What BP goal applies to most adults with hypertension?', answer: 'Below 130/80 mmHg for most adults (ACC/AHA), individualized for frailty, pregnancy, and tolerability.' },
    { prompt: 'What are the four pillars of HFrEF therapy?', answer: 'ARNI (or ACEi/ARB), evidence-based beta blocker, mineralocorticoid receptor antagonist, and SGLT2 inhibitor — plus diuretics for congestion.' },
    { prompt: 'A harsh systolic murmur radiates to the carotids and the carotid upstroke is diminished. Diagnosis?', answer: 'Aortic stenosis. Ask about angina, syncope, and dyspnea; obtain echocardiography and refer to cardiology.' },
    { prompt: 'Holosystolic murmur at the apex radiating to the axilla — which valve?', answer: 'Mitral regurgitation. Contrast with aortic stenosis (radiates to carotids) and HOCM (increases standing/Valsalva, decreases squatting).' },
    { prompt: 'Name three clues that should trigger a secondary-hypertension workup.', answer: 'Onset before 30 or after 55, resistant HTN (\u22653 drugs incl. diuretic), abrupt worsening, hypokalemia, bruits, snoring/OSA features, or episodic palpitations-headache-sweating.' },
  ],
  matrix: {
    title: 'Classify the syndrome',
    headers: ['Syndrome', 'Signature clues', 'Key test', 'FNP first move'],
    rows: [
      ['Primary HTN', 'Gradual, family history, no red flags', 'Confirm home/ABPM; BMP, lipids, A1c, ECG', 'Lifestyle + first-line drug(s); recheck 3–6 mo'],
      ['HFrEF', 'EF \u226440%, orthopnea, edema, S3', 'Echo, BNP, BMP, iron studies', 'Start/optimize the 4 pillars; daily weights'],
      ['HFpEF', 'EF \u226550%, stiff ventricle, HTN/AF', 'Echo, BNP', 'BP + volume control, SGLT2i, treat AF/OSA'],
      ['AF with RVR', 'Irregularly irregular, no P waves', 'ECG, TSH, echo, stroke-risk score', 'Rate control; anticoagulate by CHA\u2082DS\u2082-VASc'],
      ['PAD', 'Claudication, diminished pulses', 'ABI', 'Antiplatelet, statin, smoking cessation, walking program'],
    ],
  },
  patternChecks: [
    { label: 'Case A', data: 'BP 152/94 on two visits · K 4.1 · no diabetes or CKD', prompt: 'Stage the hypertension and outline first management.', answer: 'Stage 2. Start two first-line agents (e.g., ARB + amlodipine or thiazide), sodium/DASH counseling, recheck in about 1 month.' },
    { label: 'Case B', data: 'EF 30% · crackles · BNP high · BP 118/74', prompt: 'Beyond a diuretic, what four drug classes change mortality?', answer: 'ARNI/ACEi/ARB, beta blocker, MRA, and SGLT2 inhibitor. Titrate as BP, K, and renal function allow.' },
    { label: 'Case C', data: 'New AF · CHA\u2082DS\u2082-VASc 3 · HAS-BLED 1', prompt: 'Does this patient need anticoagulation?', answer: 'Yes. Stroke risk outweighs bleeding risk; a DOAC is preferred unless mechanical valve or moderate-severe mitral stenosis.' },
    { label: 'Red flag', data: 'Exertional chest pressure + syncope + harsh systolic murmur to carotids', prompt: 'What is the safest next step?', answer: 'Urgent cardiology/ED evaluation for symptomatic aortic stenosis. Avoid exertion until evaluated; echo is the key test.' },
  ],
  pearls: [
    'Confirm the cuff size and technique before labeling hypertension.',
    'An ACE cough is class-switch to ARB; angioedema is never rechallenge.',
    'In HFrEF, congestion is treated with diuretics — mortality is treated with the four pillars.',
    'A new murmur plus syncope, chest pain, or heart failure is never "watch and wait."',
  ],
}

const ENDOCRINE = {
  title: 'Diabetes, thyroid & metabolic risk',
  subtitle: 'Read the A1c · match the drug to the organ · never miss the thyroid.',
  objectives: [
    'Diagnose diabetes and prediabetes with A1c, fasting glucose, and OGTT criteria.',
    'Choose glucose-lowering therapy by ASCVD, heart failure, CKD, weight, and hypoglycemia risk.',
    'Interpret TSH/free T4 patterns and dose levothyroxine safely.',
  ],
  conceptCards: [
    { term: 'A1c', measures: 'Average glucose ~3 months', normal: '<5.7% · diabetes \u22656.5%', clue: 'Falsely changed by anemia, hemoglobin variants, recent transfusion.' },
    { term: 'Fasting glucose', measures: 'After \u22658 h fast', normal: '<100 · diabetes \u2265126 mg/dL', clue: 'Confirm on another day unless classic symptoms with random \u2265200.' },
    { term: 'TSH', measures: 'Pituitary response to T4', normal: 'Roughly 0.4–4.5 mIU/L', clue: 'High TSH + low free T4 = primary hypothyroidism.' },
    { term: 'eGFR + urine ACR', measures: 'Kidney damage in diabetes', normal: 'ACR <30 mg/g', clue: 'Drives SGLT2/ACEi-ARB decisions even when A1c is at goal.' },
  ],
  concepts: [
    { prompt: 'List the four diagnostic criteria for diabetes.', answer: 'A1c \u22656.5%, fasting glucose \u2265126 mg/dL, 2-hour OGTT \u2265200 mg/dL, or random glucose \u2265200 mg/dL with classic symptoms. Confirm asymptomatic results.' },
    { prompt: 'What A1c goal fits most nonpregnant adults, and who gets a looser goal?', answer: 'Below 7% for most. Looser (e.g., <8%) with limited life expectancy, severe hypoglycemia history, or heavy comorbidity; tighter only if safely achievable.' },
    { prompt: 'Established ASCVD or high risk — which diabetes drug classes are preferred?', answer: 'A GLP-1 receptor agonist with proven benefit and/or an SGLT2 inhibitor, independent of A1c, per ADA standards.' },
    { prompt: 'Heart failure or CKD with albuminuria — which class moves first?', answer: 'An SGLT2 inhibitor for kidney and HF protection, plus ACEi/ARB for albuminuric CKD; monitor eGFR and potassium.' },
    { prompt: 'Why is metformin still foundational, and when do you hold it?', answer: 'Low cost, weight-neutral, no hypoglycemia alone. Avoid if eGFR <30; caution/hold during acute illness or contrast risk at low eGFR; monitor B12.' },
    { prompt: 'How do you dose and monitor levothyroxine?', answer: 'Take consistently on an empty stomach, separate from iron/calcium. Recheck TSH about 6 weeks after any dose change; avoid overtreatment (AF, bone loss).' },
  ],
  matrix: {
    title: 'Match the drug to the patient',
    headers: ['Class', 'Big benefit', 'Watch out for', 'Pearl'],
    rows: [
      ['Metformin', 'First-line, weight-neutral', 'GI effects, B12, lactic acidosis risk in severe illness', 'eGFR <30: stop'],
      ['SGLT2 inhibitor', 'HF + CKD protection', 'Genital yeast, volume depletion, euglycemic DKA', 'Use even if A1c at goal when HF/CKD present'],
      ['GLP-1 RA', 'ASCVD benefit, weight loss', 'Nausea, gastroparesis, pancreatitis history', 'Weekly options aid adherence'],
      ['Sulfonylurea', 'Cheap, potent', 'Hypoglycemia, weight gain', 'Risky in older adults / erratic meals'],
      ['Insulin', 'Works at any A1c', 'Hypoglycemia, weight gain', 'Basal first in T2D; teach sick-day rules'],
    ],
  },
  patternChecks: [
    { label: 'Case A', data: 'T2D · A1c 7.4% · prior MI · eGFR 68', prompt: 'A1c is near goal — is therapy finished?', answer: 'No. Add/continue a GLP-1 RA (and/or SGLT2i) with proven ASCVD benefit independent of A1c.' },
    { label: 'Case B', data: 'T2D · A1c 8.1% · HFrEF · urine ACR 240 mg/g', prompt: 'Which add-on protects heart and kidney?', answer: 'An SGLT2 inhibitor; ensure ACEi/ARB for albuminuria and monitor BMP/potassium.' },
    { label: 'Case C', data: 'Fatigue, weight gain · TSH 18 · free T4 low', prompt: 'Diagnosis and first prescription?', answer: 'Primary hypothyroidism. Start levothyroxine (full dose if young/healthy; low and slow if older or cardiac disease).' },
    { label: 'Red flag', data: 'Vomiting, abdominal pain, Kussmaul breathing, glucose 268, anion gap high', prompt: 'What must you not miss?', answer: 'DKA can occur without extreme glucose (especially on SGLT2i). Check ketones/bicarbonate and escalate urgently.' },
  ],
  pearls: [
    'Treat the organs, not just the A1c: heart, kidney, weight, and hypoglycemia risk choose the drug.',
    'A normal A1c does not rule out diabetes when anemia or a hemoglobin variant distorts it.',
    'High TSH with normal free T4 is subclinical — treat by level, pregnancy plans, and symptoms.',
    'Recheck TSH 6 weeks after a levothyroxine change, not 6 days.',
  ],
}

const PULMONARY = {
  title: 'Asthma, COPD, pneumonia & the cough that matters',
  subtitle: 'Spirometry separates · inhalers treat · red flags escalate.',
  objectives: [
    'Use spirometry to separate obstructive from restrictive patterns.',
    'Step asthma and COPD inhaler therapy up and down safely.',
    'Risk-stratify pneumonia and choose empiric coverage and site of care.',
  ],
  conceptCards: [
    { term: 'FEV\u2081/FVC', measures: 'Airflow obstruction', normal: '<0.70 post-bronchodilator = obstruction', clue: 'Required to confirm COPD; asthma may normalize between attacks.' },
    { term: 'SABA', measures: 'Rescue bronchodilator', normal: 'Reliever only', clue: 'Frequent SABA use = uncontrolled asthma; SABA alone is not asthma treatment.' },
    { term: 'ICS', measures: 'Airway inflammation', normal: 'Controller cornerstone in asthma', clue: 'Rinse mouth after use; in COPD reserve for exacerbation/eosinophil patterns.' },
    { term: 'Pack-years', measures: '(packs/day) \u00d7 years smoked', normal: 'Screening threshold 20', clue: 'LDCT: age 50–80, \u226520 pack-years, quit <15 years ago.' },
  ],
  concepts: [
    { prompt: 'What spirometry finding confirms an obstructive defect?', answer: 'A reduced FEV\u2081/FVC ratio (<0.70 post-bronchodilator for COPD). Severity follows FEV\u2081 percent predicted; reversibility supports asthma.' },
    { prompt: 'What is the foundation of persistent asthma therapy?', answer: 'An inhaled corticosteroid-containing regimen (daily ICS or ICS-formoterol strategies per guideline), with technique and adherence checked before stepping up.' },
    { prompt: 'Which COPD patients get inhaled therapy beyond a rescue inhaler?', answer: 'Symptomatic or exacerbating patients: long-acting bronchodilators (LABA/LAMA) are the maintenance base; add ICS for frequent exacerbations with eosinophilic patterns.' },
    { prompt: 'Name the non-drug interventions that change COPD outcomes.', answer: 'Smoking cessation, vaccinations (influenza, pneumococcal, COVID, RSV/Tdap as indicated), pulmonary rehabilitation, and inhaler technique training.' },
    { prompt: 'Previously healthy outpatient with CAP and no comorbidities — empiric options?', answer: 'Amoxicillin, doxycycline, or a macrolide where resistance is low (per ATS/IDSA). Comorbidities or recent antibiotics change the regimen — add atypical coverage appropriately.' },
    { prompt: 'Who qualifies for lung cancer screening?', answer: 'Adults 50–80 with \u226520 pack-years who smoke or quit within 15 years: annual low-dose CT, with smoking-cessation counseling.' },
  ],
  matrix: {
    title: 'Classify the breathless patient',
    headers: ['Condition', 'Signature clues', 'Key test', 'FNP first move'],
    rows: [
      ['Asthma', 'Episodic wheeze, triggers, atopy, reversibility', 'Spirometry with bronchodilator', 'ICS-containing controller; action plan'],
      ['COPD', 'Progressive dyspnea, smoking/biomass exposure', 'Post-bronchodilator FEV\u2081/FVC <0.70', 'LABA/LAMA, cessation, vaccines, rehab'],
      ['Pneumonia', 'Fever, focal crackles, infiltrate', 'CXR; severity assessment', 'Empiric antibiotics by site-of-care risk'],
      ['PE', 'Pleuritic pain, tachycardia, hypoxia, leg swelling', 'D-dimer or CT angiography by probability', 'Anticoagulate/escalate urgently when suspicion is high'],
      ['Heart failure', 'Orthopnea, edema, S3, BNP up', 'BNP, CXR, echo', 'Diurese congestion; start GDMT workup'],
    ],
  },
  patternChecks: [
    { label: 'Case A', data: '24-year-old · night wheeze 3\u00d7/week · SABA canister monthly', prompt: 'Is this asthma controlled, and what changes?', answer: 'No. Frequent symptoms/SABA use means uncontrolled. Start/optimize an ICS-containing controller and give an action plan.' },
    { label: 'Case B', data: '68-year-old smoker · FEV\u2081/FVC 0.62 · two exacerbations last year', prompt: 'Diagnosis and maintenance direction?', answer: 'COPD with exacerbations. Long-acting bronchodilator(s); consider ICS by exacerbation/eosinophil pattern; cessation and vaccines are mandatory.' },
    { label: 'Case C', data: 'Fever 39\u00b0C · RR 26 · BP 96/60 · confusion · lobar infiltrate', prompt: 'Outpatient or inpatient?', answer: 'Inpatient — severity markers (hypotension, tachypnea, confusion) demand escalation, cultures, and IV therapy per local protocol.' },
    { label: 'Red flag', data: 'Sudden dyspnea · pleuritic pain · HR 118 · SpO\u2082 91% after a long flight', prompt: 'What diagnosis leads the differential?', answer: 'Pulmonary embolism. Risk-stratify and image (CTPA) or treat urgently if unstable/high probability — do not send home on reassurance.' },
  ],
  pearls: [
    'SABA-only asthma care is outdated and dangerous — every patient needs anti-inflammatory therapy.',
    'Check inhaler technique and adherence before stepping up any inhaler.',
    'A normal exam between attacks does not exclude asthma.',
    'Smoking cessation is the highest-yield prescription in COPD and lung-cancer prevention.',
  ],
}

const ANTIBIOTICS = {
  title: 'Antibiotics: coverage, allergy & stewardship',
  subtitle: 'Name the bug · pick the drug · mind the collateral damage.',
  objectives: [
    'Match common pathogens to empiric coverage by site of infection.',
    'Navigate penicillin-allergy labels without defaulting to broader drugs.',
    'Prevent C. difficile and resistance with narrow, time-limited therapy.',
  ],
  conceptCards: [
    { term: 'Empiric therapy', measures: 'Coverage before cultures return', normal: 'Based on site + likely bugs + severity', clue: 'De-escalate at 48–72 h with culture data.' },
    { term: 'MRSA coverage', measures: 'Vancomycin, doxy/TMP-SMX, linezolid (site-dependent)', normal: 'Only when risk warrants', clue: 'Prior MRSA, IVDU, severe SSTI/pneumonia patterns.' },
    { term: 'Atypicals', measures: 'Mycoplasma, Chlamydophila, Legionella', normal: 'Macrolide, doxy, or respiratory FQ', clue: 'Beta-lactams alone do not cover atypicals.' },
    { term: 'C. difficile risk', measures: 'Clindamycin, FQs, broad cephalosporins', normal: 'Highest with clindamycin', clue: 'Test only unformed stool; treat with oral vancomycin or fidaxomicin.' },
  ],
  concepts: [
    { prompt: 'A patient reports a childhood penicillin rash. Can they receive a cephalosporin?', answer: 'Usually yes. True cross-reactivity is low (~2% or less, driven by side chains, not the beta-lactam ring). Take a real allergy history; reserve avoidance for anaphylaxis/severe reactions and use shared decision-making or allergy referral.' },
    { prompt: 'Which outpatient drugs cover MRSA skin infections?', answer: 'TMP-SMX or doxycycline (clindamycin where susceptibility supports it). Incision and drainage is the primary treatment for a drainable abscess.' },
    { prompt: 'What covers Pseudomonas?', answer: 'Piperacillin-tazobactam, cefepime, meropenem, ciprofloxacin/levofloxacin, or aminoglycosides — chosen by site, severity, and local susceptibilities.' },
    { prompt: 'First-line treatment for C. difficile infection?', answer: 'Fidaxomicin preferred, oral vancomycin an alternative. Stop the inciting antibiotic when possible; avoid antimotility agents; test only symptomatic patients with unformed stool.' },
    { prompt: 'How does cephalosporin coverage change by generation?', answer: 'First generation leans gram-positive (cefazolin/cephalexin); later generations gain gram-negative coverage, with ceftriaxone a workhorse and cefepime adding Pseudomonas. Fifth-generation ceftaroline adds MRSA.' },
    { prompt: 'Name three stewardship moves on every prescription.', answer: 'Culture first when it changes management, choose the narrowest effective agent, and set the shortest effective duration with a stop/reassessment date.' },
  ],
  matrix: {
    title: 'Match coverage to the bug',
    headers: ['Need', 'Think of', 'Typical agents', 'Caution'],
    rows: [
      ['Strep / MSSA skin', 'Cellulitis, impetigo', 'Cephalexin, dicloxacillin', 'Add MRSA cover only with risk factors or failure'],
      ['MRSA', 'Abscess, prior MRSA, IVDU', 'TMP-SMX, doxycycline; IV vancomycin if severe', 'Drain abscesses — antibiotics alone fail pus'],
      ['Atypicals', 'CAP, "walking pneumonia"', 'Doxycycline, azithromycin, respiratory FQ', 'QT prolongation with macrolides/FQs'],
      ['Pseudomonas', 'Hospital-acquired, structural lung disease', 'Cefepime, pip-tazo, meropenem, cipro', 'Confirm risk before going this broad outpatient'],
      ['Anaerobes', 'Aspiration, intra-abdominal, bites', 'Metronidazole combos, amox-clav, pip-tazo', 'Amox-clav is the bite workhorse'],
    ],
  },
  patternChecks: [
    { label: 'Case A', data: 'Fluctuant 3 cm abscess · afebrile · no cellulitis', prompt: 'Antibiotic first, or procedure first?', answer: 'Incision and drainage first. Add an MRSA-active antibiotic for size, systemic signs, immunocompromise, or surrounding cellulitis per guideline.' },
    { label: 'Case B', data: 'CAP outpatient · was on amoxicillin last month', prompt: 'Why not simply repeat amoxicillin?', answer: 'Recent same-class exposure raises resistance risk. Choose an alternative regimen with appropriate typical + atypical coverage per ATS/IDSA and comorbidities.' },
    { label: 'Case C', data: 'Watery diarrhea + cramps 10 days after clindamycin', prompt: 'Diagnosis and first steps?', answer: 'C. difficile until proven otherwise. Test unformed stool, stop inciting antibiotics, start fidaxomicin or oral vancomycin, institute contact precautions.' },
    { label: 'Red flag', data: '"Penicillin anaphylaxis" label · needs surgical prophylaxis', prompt: 'Safest approach?', answer: 'Do not casually give a beta-lactam. Clarify the reaction, involve pharmacy/allergy, and select an accepted alternative (e.g., vancomycin or clindamycin per protocol).' },
  ],
  pearls: [
    'Most "penicillin allergy" labels are wrong — a good history is a stewardship intervention.',
    'Pus needs drainage; antibiotics are the supporting act.',
    'Recent antibiotic exposure (90 days) changes empiric choices.',
    'Every antibiotic order needs an indication, a drug, and a duration.',
  ],
}

const BLUEPRINTS = { hematology: HEMATOLOGY, 'cardiovascular-and-peripheral-vascular-disorders': CARDIOLOGY, 'endocrine-disorders': ENDOCRINE, 'pulmonary-disorders': PULMONARY, antibiotics: ANTIBIOTICS }

export function curatedChapterIds() { return Object.keys(BLUEPRINTS) }

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

  const listConcepts = []
  chapter.sections.forEach(section => {
    if (/practice questions/i.test(section.title)) return
    ;(section.blocks || []).forEach(block => {
      if (block.type !== 'list' || !Array.isArray(block.items)) return
      const items = block.items.map(clean).filter(item => item.length > 8 && item.length < 220)
      if (items.length < 3 || listConcepts.length >= 6) return
      const name = clean(section.title)
      if (!name || name.length > 65) return
      listConcepts.push({
        prompt: `What must an FNP recall about ${name.charAt(0).toLowerCase() + name.slice(1)}?`,
        answer: items.slice(0, 8).join(' · '),
      })
    })
  })

  return {
    title: `${title}: clinical reasoning workbook`,
    subtitle: 'Move from key findings to diagnosis, treatment, and follow-up.',
    objectives: [
      `Recognize the common presentations and red flags in ${title}.`,
      'Select the most appropriate diagnostic test or clinical next step.',
      'Choose first-line management and know when referral is required.',
    ],
    concepts: listConcepts.length >= 3 ? listConcepts : sectionNames.map(name => ({
      prompt: `For ${name}, what presentation, diagnostic clue, and first-line action should an FNP know?`,
      answer: `Build a concise presentation \u2192 diagnosis \u2192 management summary for ${name} from the chapter tables and board questions below.`,
    })),
    matrix: tables[0] || null,
    patternChecks: [],
    pearls: [],
    tables,
  }
}

