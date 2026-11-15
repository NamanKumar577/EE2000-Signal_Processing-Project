"""Completeness check of the bibliography in fpr-8.tex (authors, year, DOI or URL). No web access."""
import re
from pathlib import Path

TEX = Path(__file__).resolve().parents[2] / "report/final_report/fpr-8.tex"
OUT = Path(__file__).resolve().parent / "out/reference_audit.md"
s = TEX.read_text(encoding="utf-8")
bib = s[s.index("\\begin{thebibliography}"):s.index("\\end{thebibliography}")]
items = re.split(r"\\bibitem\{", bib)[1:]
lines = ["# Reference audit (completeness only; links not opened)", "", "| key | authors | year | DOI/URL | DOI | note |", "|---|---|---|---|---|---|"]
problems = []
for it in items:
    key = it[:it.index("}")]
    text = it[it.index("}") + 1:]
    first = text.strip().split("\\newblock")[0]
    org = re.search(r"Anthropic|OpenAI|Google|PhysioNet|RealDigital|Xilinx|AMD", first)
    authors = bool(re.search(r"[A-Z][a-z]+", first)) and len(first.strip()) > 3
    year = bool(re.search(r"(19|20)\d\d", text))
    url = "\\url{" in text or "doi" in text.lower()
    doi = "doi.org" in text or "DOI" in text
    note = "organisation as author" if org else ""
    if not (authors and year and url):
        problems.append(key)
    lines.append(f"| {key} | {'yes' if authors else 'NO'} | {'yes' if year else 'NO'} | {'yes' if url else 'NO'} | {'yes' if doi else 'no'} | {note} |")
lines += ["", f"{len(items)} references; incomplete (missing authors, year or link): {', '.join(problems) or 'none'}.",
          "References without a DOI rely on a URL; none of the links were opened in this check (no web access), so their targets are unverified here."]
OUT.write_text("\n".join(lines), encoding="utf-8")
print(len(items), "refs; incomplete:", problems)
print("without DOI:", [l.split('|')[1].strip() for l in lines[4:4 + len(items)] if l.split('|')[5].strip() == 'no'])
