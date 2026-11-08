#!/usr/bin/env python3
"""Convert APEA docx -> src/data/guide.json preserving document order (paras + tables)."""
import re, json, sys
from pathlib import Path
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

SRC = sys.argv[1] if len(sys.argv)>1 else "/home/ubuntu/.cursor/projects/workspace/uploads/APEA_2026_FNP_Complete_Study_Guide_a015.docx"
OUT = Path(__file__).resolve().parent.parent / "src/data/guide.json"

def slug(s):
    return re.sub(r'[^a-z0-9]+','-', s.lower()).strip('-')[:60]

doc = Document(SRC)
chapters=[]; chapter=None; section=None
def ensure_section():
    global section
    if chapter is None: return None
    if section is None:
        section={"id": slug(chapter["title"])+"-intro","title":"Overview","blocks":[]}
        chapter["sections"].append(section)
    return section

for child in doc.element.body.iterchildren():
    if child.tag.endswith('}p'):
        p=Paragraph(child, doc); t=p.text.strip(); style=p.style.name if p.style else ""
        if not t: continue
        if style=="Title" or (style=="Heading 1"):
            continue
        if style=="Heading 2":
            chapter={"id": slug(re.sub(r'^\d+\.\s*','',t)),"title":t,"sections":[],"questions":[]}
            chapters.append(chapter); section=None; continue
        if chapter is None: continue
        if style=="Heading 3":
            section={"id": slug(chapter["title"])+"-"+slug(t),"title":t,"blocks":[]}
            chapter["sections"].append(section); continue
        s=ensure_section()
        if s is None: continue
        if style=="List Paragraph":
            # merge consecutive list items into one block
            if s["blocks"] and s["blocks"][-1]["type"]=="list":
                s["blocks"][-1]["items"].append(t)
            else:
                s["blocks"].append({"type":"list","items":[t]})
        else:
            s["blocks"].append({"type":"p","text":t})
    elif child.tag.endswith('}tbl'):
        if chapter is None: continue
        s=ensure_section()
        if s is None: continue
        tbl=Table(child, doc)
        rows=[[c.text.strip() for c in r.cells] for r in tbl.rows]
        rows=[r for r in rows if any(r)]
        if rows:
            s["blocks"].append({"type":"table","headers":rows[0],"rows":rows[1:]})

# ---- parse questions + answers ----
QRE=re.compile(r'^Q(\d+)\s*[.\u2013-]\s*(.*)$', re.S)
OPTRE=re.compile(r'\((\d+)\)\s*')
def parse_question(text, ch, n_fallback):
    m=QRE.match(text.strip())
    if not m: return None
    body=m.group(2)
    parts=OPTRE.split(body)
    # parts: [stem, num, opt, num, opt...]
    stem=parts[0].strip()
    options=[]
    if len(parts)>=5:
        for i in range(1,len(parts)-1,2):
            options.append(parts[i+1].strip())
    return {"stem":stem,"options":options}

answer_map={}  # short heading -> list of raw answer strings
for ch in chapters:
    if ch["title"].startswith("Answer Key"):
        for sec in ch["sections"]:
            ans=[]
            for b in sec["blocks"]:
                if b["type"]=="list": ans.extend(b["items"])
                elif b["type"]=="p" and not b["text"].startswith("Answers give"): ans.append(b["text"])
            answer_map[sec["title"]]=ans

# map chapter title -> answer heading (fuzzy by keywords)
ALIASES={"neurologic":"Neurology","orthopedic":"Orthopedics","eye, ear":"EENT","urology":"Urology & STI"}
def find_answers(ch):
    title=ch["title"].lower()
    for frag,heading in ALIASES.items():
        if frag in title and heading in answer_map: return answer_map[heading]
    for k,v in answer_map.items():
        kl=k.lower()
        if kl in title or any(w in title for w in kl.replace('&',' ').split() if len(w)>4):
            return v
    return []

stats=[]
for ch in chapters:
    if ch["title"].startswith(("Answer Key",)): continue
    raw=[]
    for sec in ch["sections"]:
        if sec["title"].lower().startswith("practice questions"):
            for b in sec["blocks"]:
                texts = b["items"] if b["type"]=="list" else [b["text"]] if b["type"]=="p" else []
                for t in texts:
                    q=parse_question(t, ch, len(raw)+1)
                    if q: raw.append(q)
    answers=find_answers(ch)
    questions=[]
    for i,q in enumerate(raw):
        a = answers[i] if i < len(answers) else ""
        correct=None; expl=a
        m=re.match(r'^\((\d+)\)\s*', a)
        if m:
            correct=int(m.group(1))-1
            expl=a[m.end():].strip() or a
        questions.append({"id": f"{ch['id']}-q{i+1}","chapterId":ch["id"],"n":i+1,
                          "stem":q["stem"],"options":q["options"],
                          "correctIndex":correct,"explanation":expl})
    ch["questions"]=questions
    if raw or answers: stats.append(f"{ch['title']}: questions={len(raw)} answers={len(answers)} graded={sum(1 for q in questions if q['correctIndex'] is not None)}")

# split special chapters
regular=[c for c in chapters if not c["title"].startswith("Answer Key")]
quick=[c for c in regular if c["title"].startswith("High-Yield")]
regular=[c for c in regular if not c["title"].startswith("High-Yield")]
for i,c in enumerate(regular):
    m=re.match(r'^(\d+)\.\s*(.*)$', c["title"])
    c["number"]=int(m.group(1)) if m else i+1
    c["shortTitle"]=m.group(2) if m else c["title"]
    c["wordCount"]=sum(len(b.get("text","").split())+sum(len(x.split()) for x in b.get("items",[])) for s in c["sections"] for b in s["blocks"])

out={"meta":{"title":"APEA 2026 FNP Complete Study Guide","source":"APEA_2026_FNP_Complete_Study_Guide_a015.docx",
             "chapters":len(regular),"questions":sum(len(c["questions"]) for c in regular)},
     "chapters":regular,"quickRef": quick[0] if quick else None}
OUT.write_text(json.dumps(out, ensure_ascii=False))
print("\n".join(stats))
print(f"Wrote {OUT} chapters={len(regular)} questions={out['meta']['questions']} size={OUT.stat().st_size//1024}KB quickRef={'yes' if quick else 'no'}")
