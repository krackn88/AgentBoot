#!/usr/bin/env python3
"""Append overrides for remaining ungraded manual slide MCQs."""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "public/data/guide.json"
MANUAL = ROOT / "public/data/manual-questions.json"
OVERRIDES = ROOT / "public/data/manual-question-overrides.json"

# Verified against slide stems / Answer Key alignment (remaining ambiguous bank).
CURATED = {
    "manual-04-q9": {"correctIndex": 2, "explanation": "Quitting smoking slows progression but does not prevent all symptom worsening in established COPD."},
    "manual-04-q12": {"correctIndex": 0, "explanation": "Symptomatic COPD: short-acting bronchodilator (e.g. ipratropium/albuterol) per GOLD staging."},
    "manual-05-q6": {"correctIndex": 2, "explanation": "Treat menorrhagia cause or IDA persists despite iron."},
    "manual-06-q2": {"correctIndex": 2, "explanation": "Positive Dix–Hallpike with brief nystagmus supports BPPV."},
    "manual-06-q9": {"correctIndex": 0, "explanation": "Duration/severity of hyperglycemia drives diabetic neuropathy risk."},
    "manual-07-q5": {"correctIndex": 3, "explanation": "First MDD episode: continue antidepressant ≥6 months after remission."},
    "manual-07-q6": {"correctIndex": 3, "explanation": "SSRI nonresponse: switch class (e.g. SNRI) or augment — not tricyclic first line."},
    "manual-07-q7": {"correctIndex": 1, "explanation": "St. John's wort interacts with serotonergic drugs — serotonin syndrome risk."},
    "manual-07-q8": {"correctIndex": 0, "explanation": "PTSD first-line: trauma-focused psychotherapy ± SSRI/SNRI."},
    "manual-07-q9": {"correctIndex": 2, "explanation": "Active substance use disorder complicates stimulant ADHD treatment."},
    "manual-08-q2": {"correctIndex": 1, "explanation": "Murphy sign: inspiratory arrest with RUQ palpation in cholecystitis."},
    "manual-08-q7": {"correctIndex": 3, "explanation": "GERD controlled: trial PPI discontinuation to assess ongoing need."},
    "manual-08-q8": {"correctIndex": 1, "explanation": "Chronic GERD in older smoker: consider Barrett's and malignancy."},
    "manual-09-q1": {"correctIndex": 3, "explanation": "Asymptomatic bacteriuria: treat in pregnancy only."},
    "manual-09-q3": {"correctIndex": 3, "explanation": "Empiric UTI failure: switch agent and extend course (e.g. nitrofurantoin)."},
    "manual-09-q6": {"correctIndex": 3, "explanation": "IC/PBS: avoid bladder irritants; multimodal conservative care."},
    "manual-09-q7": {"correctIndex": 3, "explanation": "Dysuria + discharge: STI testing before empiric antibiotics only."},
    "manual-09-q10": {"correctIndex": 3, "explanation": "PID can present subtly: dyspareunia, abnormal bleeding, pelvic pain."},
    "manual-09-q15": {"correctIndex": 2, "explanation": "HIV screening: HIV-1/2 Ag/Ab combination assay first."},
    "manual-10-q3": {"correctIndex": 2, "explanation": "Uncontrolled on chlorthalidone 12.5 mg: increase thiazide dose."},
    "manual-10-q5": {"correctIndex": 3, "explanation": "Uncomplicated HTN: thiazide/CCB/ACE/ARB — chlorthalidone is appropriate."},
    "manual-10-q6": {"correctIndex": 3, "explanation": "Resistant HTN despite combination therapy suggests secondary causes."},
    "manual-10-q7": {"correctIndex": 2, "explanation": "Calculate ASCVD risk before statin intensity."},
    "manual-10-q12": {"correctIndex": 3, "explanation": "Intermittent palpitations: CHA2DS2-VASc for stroke risk and anticoagulation."},
    "manual-10-q19": {"correctIndex": 1, "explanation": "PAD: exertional leg pain relieved by rest (claudication)."},
    "manual-11-q4": {"correctIndex": 3, "explanation": "Diabetes range labs: diagnose and initiate treatment plus lifestyle."},
    "manual-11-q6": {"correctIndex": 0, "explanation": "Metformin contraindicated when eGFR <30; caution 30–45."},
    "manual-11-q7": {"correctIndex": 2, "explanation": "GLP-1: weight may return after discontinuation."},
    "manual-11-q9": {"correctIndex": 3, "explanation": "Triple oral therapy failing: add basal insulin without dropping metformin/GLP-1."},
    "manual-11-q10": {"correctIndex": 2, "explanation": "Basal insulin: titrate up if fasting glucose above goal."},
    "manual-11-q13": {"correctIndex": 0, "explanation": "Subclinical hypothyroidism: repeat TSH in 6–12 months if asymptomatic."},
    "manual-11-q15": {"correctIndex": 2, "explanation": "Persistent elevated TSH on levothyroxine: increase dose and recheck."},
    "manual-12-q1": {"correctIndex": 1, "explanation": "Dense breasts + older nulliparous female: higher breast cancer risk."},
    "manual-12-q6": {"correctIndex": 2, "explanation": "Recurrent VVC: evaluate for immunocompromise."},
    "manual-13-q4": {"correctIndex": 3, "explanation": "Older male LUTS most often BPH."},
    "manual-13-q8": {"correctIndex": 1, "explanation": "Nitrates absolutely contraindicated with PDE5 inhibitors."},
    "manual-13-q10": {"correctIndex": 1, "explanation": "Acute scrotum in teen: TWIST score and emergency urology."},
    "manual-16-q11": {"correctIndex": 3, "explanation": "Ménière disease can cause permanent sensorineural hearing loss."},
    "manual-17-q5": {"correctIndex": 3, "explanation": "Creatinine trends need context (hydration, meds) before labeling chronicity."},
    "manual-17-q9": {"correctIndex": 3, "explanation": "Orthostatic hypotension confirmed with orthostatic vital signs."},
    "manual-18-q3": {"correctIndex": 1, "explanation": "Folic acid prevents neural tube defects such as spina bifida."},
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower())


def map_index(guide_correct: str, manual_options: list[str]) -> int | None:
    g = norm(guide_correct)
    best_i, best_r = None, 0.0
    for i, opt in enumerate(manual_options):
        o = norm(opt)
        r = SequenceMatcher(None, g[:70], o[:70]).ratio()
        if g in o:
            r = 0.95
        if r > best_r:
            best_r = r
            best_i = i
    return best_i if best_r >= 0.5 else None


def main():
    guide = json.loads(GUIDE.read_text())
    manual = json.loads(MANUAL.read_text())
    overrides = json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {"set": []}
    have = {x["id"] for x in overrides["set"]}
    ungraded = {q["id"] for q in manual["questions"] if q["correctIndex"] is None}
    added = 0

    for qid, data in CURATED.items():
        if qid not in ungraded or qid in have:
            continue
        overrides["set"].append({"id": qid, **data, "source": "curated-final"})
        have.add(qid)
        added += 1

    by_ch = {ch["id"]: ch.get("questions", []) for ch in guide["chapters"]}
    for mq in manual["questions"]:
        if mq["id"] not in ungraded or mq["id"] in have:
            continue
        best_gq, best_r = None, 0.0
        for gq in by_ch.get(mq["chapterId"], []):
            if gq.get("correctIndex") is None:
                continue
            r = SequenceMatcher(None, norm(mq["stem"][:140]), norm(gq["stem"][:140])).ratio()
            if r > best_r:
                best_r = r
                best_gq = gq
        if best_gq and best_r >= 0.4:
            gi = best_gq["correctIndex"]
            idx = map_index(best_gq["options"][gi], mq["options"])
            if idx is None and len(mq["options"]) == len(best_gq["options"]):
                idx = gi
            if idx is not None:
                overrides["set"].append({
                    "id": mq["id"],
                    "correctIndex": idx,
                    "explanation": (best_gq.get("explanation") or "")[:500],
                    "source": f"auto-sync r={best_r:.2f}",
                })
                have.add(mq["id"])
                added += 1

    OVERRIDES.write_text(json.dumps(overrides, ensure_ascii=False, indent=2) + "\n")
    print(f"Added {added} overrides; total {len(overrides['set'])}")


if __name__ == "__main__":
    main()
