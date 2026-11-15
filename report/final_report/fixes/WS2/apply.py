"""WS2: replace Sec. 12 by \\input{sections/ws2_literature}, correct three bibitems, add one. Exact unique matches."""
from pathlib import Path

p = Path(__file__).resolve().parents[2] / "fpr-8.tex"
s = p.read_text(encoding="utf-8")


def sub(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (n, old[:80])
    s = s.replace(old, new)


# 1. Sec. 12 body -> input (from the section heading up to the comment rule before the next section)
i = s.index("\\section{Extended Literature Survey and Taxonomic Positioning}")
j = s.index("% =====================================================================", i)
s = s[:i] + "\\input{sections/ws2_literature}\n\n" + s[j:]

# 2. edwin2022: the cited title/DOI did not exist; correct record (Crossref 10.1109/TBCAS.2022.3204993)
i = s.index("\\bibitem{edwin2022}")
j = s.index("\\bibitem{", i + 5)
s = s[:i] + ("\\bibitem{edwin2022}\n\\fin{D.~Edwin~Dhas and M.~Suchetha.\n"
             "\\newblock Extraction of fetal ECG from abdominal and thorax ECG using a non-causal adaptive filter architecture.\n"
             "\\newblock {\\em IEEE Transactions on Biomedical Circuits and Systems}, 16(5):981--990, 2022. "
             "\\url{https://doi.org/10.1109/TBCAS.2022.3204993}}\n\n") + s[j:]

# 3. pani2016: no such paper found (DOI resolved to another article); replace by the verified group paper
i = s.index("\\bibitem{pani2016}")
j = s.index("\\bibitem{", i + 5)
s = s[:i] + ("\\bibitem{muceli2007}\n\\fin{S.~Muceli, D.~Pani, and L.~Raffo.\n"
             "\\newblock Real-time foetal ECG extraction with JADE on floating point DSP.\n"
             "\\newblock {\\em Electronics Letters}, 43(18):963--965, 2007. \\url{https://doi.org/10.1049/el:20071331}}\n\n"
             "\\bibitem{vasudeva2020}\n\\fin{B.~Vasudeva, P.~Deora, P.~M. Pradhan, and S.~Dasgupta.\n"
             "\\newblock Efficient implementation of LMS adaptive filter-based FECG extraction on an FPGA.\n"
             "\\newblock {\\em Healthcare Technology Letters}, 7(5):125--131, 2020. \\url{https://doi.org/10.1049/htl.2020.0016}}\n\n") + s[j:]
n = s.count("pani2016")
s = s.replace("pani2016", "muceli2007")
print("renamed pani2016 citations:", n)

# 4. delathauwer2000: wrong DOI (resolved to an unrelated paper); correct DOI from Crossref
sub("\\url{https://doi.org/10.1109/10.841333}", "\\url{https://doi.org/10.1109/10.841326}")

p.write_text(s, encoding="utf-8", newline="")
print("WS2 applied")
