import json
from pathlib import Path
from list_captions import TEX
p = Path(__file__).resolve().parent / "out/patches_task7.json"
P = json.loads(p.read_text(encoding="utf-8"))
s = TEX.read_text(encoding="utf-8")
old = "\\newblock Xilinx, San Jose, CA, v1.10 edition, 2018.\n"
assert s.count(old) == 1
if not any(x["old"] == old for x in P):
    P.append(dict(old=old, new="\\newblock Xilinx, San Jose, CA, v1.10 edition, 2018. \\url{https://docs.amd.com/v/u/en-US/ug479_7Series_DSP48E1}\n",
                  why="reference had no DOI or URL (URL not opened; verify before submission)"))
p.write_text(json.dumps(P, indent=1), encoding="utf-8")
print(len(P), "patches")
