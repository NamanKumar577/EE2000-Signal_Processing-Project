"""Make long file paths in sections/repro.tex breakable: \texttt{a/b\_c} -> \path{a/b_c} (only paths without braces)."""
import re
from pathlib import Path

p = Path(__file__).resolve().parents[2] / "sections" / __import__("sys").argv[1]
s = p.read_text(encoding="utf-8")


def conv(m):
    t = m.group(1)
    if "/" not in t or "\\{" in t or "$" in t:
        return m.group(0)
    return "\\path{" + t.replace("\\_", "_").replace("\\#", "#").replace("\\&", "&") + "}"


s2, n = re.subn(r"\\texttt\{([^{}]*)\}", conv, s)
p.write_text(s2, encoding="utf-8", newline="")
print("converted", n)
