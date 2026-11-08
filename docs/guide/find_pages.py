import sys, json, pdfplumber
ids = json.load(open(sys.argv[2])); out = {}
with pdfplumber.open(sys.argv[1]) as pdf:
    texts = [(p.extract_text() or '') for p in pdf.pages]
for sid, title in ids:
    for i, t in enumerate(texts):
        if i < 2:
            continue                       # cover + table of contents
        lines = [l.strip() for l in t.split('\n')[:4]]
        if any(l == title or l.startswith(title) for l in lines):
            out[sid] = i + 1; break
print(json.dumps(out))
