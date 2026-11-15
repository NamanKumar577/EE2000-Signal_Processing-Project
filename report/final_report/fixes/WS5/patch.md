# WS5 patch (applied by apply.py; old text quoted exactly there)

1. fpr-8.tex, Table 1 (tab:clinical_specs), row "Clinical agreement": `not measured for the final design & -- & --`
   -> `CinC test 67.6%, CinC dev 78.2%, ADFECGDB 92.3%, FECGSYNDB subset 90.6% & Not met & L5 (C model, bit-exact)`.
2. fpr-8.tex, Future Work, spatio-temporal sentence: source `tools/accuracy/_taps/results.csv` (variants k2d1, k3d1) added.
3. sections/analysis.tex (a): "real recordings were not checked ..." -> FPGA-maternal-peak proxy, 20.1 % vs 20.8 % (CinC dev), 19.8 % vs 20.0 % (ADFECGDB).
4. sections/analysis.tex (b): label "not checked" -> "checked against data"; closing sentence -> 15,610 solves, J = lambda_max within 1.4e-10, byte-identical logging copy.
5. sections/hardware.tex: "Not done" paragraph -> negative controls (a) and (b), optional Vivado strategy paragraph, shortened "Not done".
6. sections/limitations_items.tex: "Not measured" list shortened; pointer to the new checks.
