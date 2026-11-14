import sys
from pathlib import Path

p = Path(sys.argv[1])
lines = p.read_text(encoding="utf-8").split("\n")
out, n_prompt, n_answer, i = [], 0, 0, 0
while i < len(lines):
    ln = lines[i]
    if ln.startswith("> ok make final changes in  the report") and "tell about them." in ln:
        out += [ln[: ln.index("tell about them.") + len("tell about them.")],
                "> [rest of this prompt omitted: not about the project or the report]"]
        n_prompt += 1
        i += 1
        continue
    if ln.startswith("> Your questions have been answered:") and "team folder" in ln:
        # the whole answer block (quoted lines up to the next blank line) is about the omitted part
        while i < len(lines) and lines[i].startswith(">"):
            i += 1
        out.append("> [answer omitted: about the omitted part of the previous prompt, not about the project or the report]")
        n_answer += 1
        continue
    out.append(ln)
    i += 1
assert n_prompt == 1 and n_answer == 1, (n_prompt, n_answer)
p.write_text("\n".join(out), encoding="utf-8")
print("cut applied")
