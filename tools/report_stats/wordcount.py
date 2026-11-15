"""Approximate word count of report/final_report/fpr-8.tex per section (LaTeX commands, math and comments stripped)."""
import re
import sys
from pathlib import Path

TEX = Path(__file__).resolve().parents[2] / "report/final_report/fpr-8.tex"


def words(t):
    t = re.sub(r"(?<!\\)%.*", "", t)                      # comments
    t = re.sub(r"\$[^$]*\$", " x ", t)                      # inline math = one token
    t = re.sub(r"\\begin\{(equation|align)\*?\}.*?\\end\{\1\*?\}", " ", t, flags=re.S)
    t = re.sub(r"\\[a-zA-Z@]+\*?(\[[^\]]*\])?", " ", t)   # commands
    t = re.sub(r"[{}&\\~]", " ", t)
    return len(re.findall(r"[A-Za-z0-9][\w.\-]*", t))


s = TEX.read_text(encoding="utf-8")
body = s[s.index("\\begin{document}"):s.index("\\begin{thebibliography}")]
app = s[s.index("\\appendix"):] if "\\appendix" in s else ""
parts = re.split(r"(?=\\section\{)", body)
total = 0
for p in parts:
    m = re.match(r"\\section\{([^}]*)\}", p)
    n = words(p)
    total += n
    if len(sys.argv) > 1:
        print(f"{n:6d}  {(m.group(1) if m else 'front matter')[:70]}")
print(f"main text {total} words; appendix {words(app)} words; total {total + words(app)}")
