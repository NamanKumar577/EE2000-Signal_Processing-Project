# WS2 patch

Applied by `fixes/WS2/apply.py` (exact unique matches, asserts on failure).

1. fpr-8.tex: the block from
   `\section{Extended Literature Survey and Taxonomic Positioning}` up to the next `% =====` comment rule
   (old text: six-item list "Linear Adaptive Filtering ... delivering deterministic single-DSP edge execution.")
   -> `\input{sections/ws2_literature}` (new file `sections/ws2_literature.tex`, full text there).
2. `\bibitem{edwin2022}` entry -> corrected title/DOI 10.1109/TBCAS.2022.3204993.
3. `\bibitem{pani2016}` entry -> `\bibitem{muceli2007}` (Electronics Letters 43(18):963-965, 2007) + new `\bibitem{vasudeva2020}` (Healthcare Technology Letters 7(5):125-131, 2020); all `pani2016` citations -> `muceli2007`.
4. `\url{https://doi.org/10.1109/10.841333}` -> `\url{https://doi.org/10.1109/10.841326}` (delathauwer2000).
