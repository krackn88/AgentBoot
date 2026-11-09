#!/usr/bin/env python3
"""Assign each must-know rule pearl to the chapter it actually belongs to.

Every pearl previously inherited the same chapterId (the quick-reference page),
so per-chapter pearl tabs were empty and the deck looked like one giant list.
Topical keywords map each rule to a guide chapter; anything unmatched stays in a
general bucket rather than being mislabelled.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "public/data"
SRC = DATA / "pearls-clean.json"
GUIDE = json.loads((DATA / "guide.json").read_text())

# topic -> chapter id, checked in order
RULES = [
    (r"\b(vaccine|immuniz|shingrix|tdap|rsv|pcv|ppsv|hepatitis|flu)\b", "exam-prep-and-how-to-use-this-guide"),
    (r"\b(aom|otitis|strep|pharyng|abrs|sinusitis|bites?|lyme|zoster|antibiotic|penicillin|doxycycline|amoxicillin)\b", "antibiotics"),
    (r"\b(ottawa|knee|gout|ra\b|rheumatoid|fibromyalgia|lbp|low back|fracture|orthoped)\b", "orthopedic-disorders"),
    (r"\b(pregnan|gdm|rhogam|gbs|group b|preeclampsia|folic acid|trimester|postpartum)\b", "pregnancy-in-primary-care"),
    (r"\b(infant|fontanel|peds|pediatric|child|toddler|adolescent|newborn)\b", "pediatrics"),
    (r"\b(ckd|egfr|uacr|renal|kidney)\b", "urology-and-sexually-transmitted-infections"),
    (r"\b(orthostatic|hypotension|hypertens|bp\b|blood pressure|cardiovascular|afib|statin|ldl)\b", "cardiovascular-and-peripheral-vascular-disorders"),
    (r"\b(frailty|fried|aging|older adult|elder|geriatric|cognit)\b", "care-of-the-aging-adult"),
    (r"\b(diabet|a1c|glycem|insulin|thyroid|tsh|endocrine|glucose)\b", "endocrine-disorders"),
    (r"\b(depress|anxiety|ssri|mental|phq|gad)\b", "mental-health-in-primary-care"),
    (r"\b(anemia|hemoglobin|ferritin|platelet|coagul|inr|cbc)\b", "hematology"),
    (r"\b(asthma|copd|pneumonia|curb|spiromet|cough|dyspnea|pulmon)\b", "pulmonary-disorders"),
    (r"\b(gerd|ppl|ppi|h2 blocker|ulcer|constipat|diarrhea|gastro|ibd|liver)\b", "gastrointestinal-disorders"),
    (r"\b(stroke|seizure|migraine|headache|neuro|vertigo|triptan)\b", "neurologic-disorders"),
    (r"\b(rash|dermat|acne|psoriasis|eczema|lesion)\b", "dermatology"),
    (r"\b(eye|ear\b|nose|throat|eent|conjunctiv|hearing|vision)\b", "eye-ear-nose-and-throat-eent"),
    (r"\b(bph|prostat|testoster|men'?s health|erectile)\b", "men-s-health"),
    (r"\b(women|menstrual|contracept|menopaus|pap|hpv|endometrios)\b", "women-s-health"),
    (r"\b(certification|malpractice|negligence|licens|credential|dea\b|npi\b|contract)\b", "entry-into-practice"),
    (r"\b(ethics|advocacy|policy|scope of practice|evidence|research|theory)\b", "professional-role-competencies-issues"),
    (r"\b(growth|development|milestone|screen time)\b", "pediatric-growth-development"),
]

CHAPTER_IDS = {c["id"] for c in GUIDE["chapters"]}
TITLES = {c["id"]: (c.get("shortTitle") or c.get("title")) for c in GUIDE["chapters"]}


def assign(text: str):
    low = text.lower()
    for pattern, chapter in RULES:
        if chapter in CHAPTER_IDS and re.search(pattern, low, re.I):
            return chapter
    return None


def main() -> int:
    data = json.loads(SRC.read_text())
    moved = 0
    general = 0
    for p in data["pearls"]:
        # rationale pearls already know their chapter - trust it over keyword guesses
        if p.get("kind") == "rationale" and p.get("chapterId") in CHAPTER_IDS:
            continue
        target = assign(p["front"])
        if target and target != p["chapterId"]:
            p["chapterId"] = target
            p["tag"] = TITLES.get(target, p["tag"])
            p["back"] = f"{p['tag']} — board pearl. Say it out loud once, then flip."
            moved += 1
        elif not target:
            p["chapterId"] = "exam-prep-and-how-to-use-this-guide"
            p["tag"] = "Must-know rules"
            p["back"] = "Must-know rule — say it out loud once, then flip."
            general += 1

    from collections import Counter
    counts = Counter(p["chapterId"] for p in data["pearls"])
    data["meta"]["assigned"] = moved
    data["meta"]["general"] = general
    SRC.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print(f"assigned {moved} pearls to topical chapters · {general} kept in the general bucket")
    for cid, n in counts.most_common():
        print(f"  {n:>3}  {TITLES.get(cid, cid)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
