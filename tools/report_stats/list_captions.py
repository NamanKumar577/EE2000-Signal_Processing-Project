"""List captions of fpr-8.tex with their label and whether they carry a level tag."""
import re
from pathlib import Path

TEX = Path(__file__).resolve().parents[2] / "report/final_report/fpr-8.tex"


def captions(s):
    for m in re.finditer(r"\\caption\{", s):
        i = m.end(); depth = 1; j = i
        while depth:
            c = s[j]
            if c == "\\":
                j += 2; continue
            depth += (c == "{") - (c == "}")
            j += 1
        body = s[i:j - 1]
        lab = re.search(r"\\label\{([^}]*)\}", s[j:j + 300])
        yield m.start(), j - 1, body, lab.group(1) if lab else "?"


if __name__ == "__main__":
    s = TEX.read_text(encoding="utf-8")
    for a, b, body, lab in captions(s):
        tagged = bool(re.search(r"\\tagL|\[L[1-5]", body))
        print(f"{lab:28s} tagged={tagged} blue={'fb' in body[:6]} | {body[:90]!r}")
