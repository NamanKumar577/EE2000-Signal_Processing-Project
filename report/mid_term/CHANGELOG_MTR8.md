# CHANGELOG_MTR8: Comprehensive Mid-Term Report Audit and Fix Log

This log documents every correction made to `mtr-8.pdf`, `mtr-8.tex`, and associated scripts in accordance with `MTR8_audit_and_fix_plan.md` and `MTR8_v2_audit_python_theory.md`.

Format: `ID | File | Before -> After | Evidence`

---

## 1. P0 Priority Items (Audit V2)

| ID | File | Before -> After | Evidence |
|---|---|---|---|
| **S-01** | `build_full_report.py`, `mtr-8.tex` | Stated lead selection used "all recordings" while claiming held-out test set untouched -> Corrected: Lead selection evaluated strictly on training partition (`sub01`--`sub07`), selecting 0-based suprapubic channels $[27, 26, 28, 25]$ (1-based $[28, 27, 29, 26]$), leaving `sub09`--`sub10` completely untouched | Diagnostic script `diagnostics_mtr8_v2.py` confirms suprapubic leads peak across training partition with FMR $0.23 - 0.46$ vs thoracic $0.024$ |
| **S-02** | `build_full_report.py`, `mtr-8.tex` | U-Net scored higher on unseen test subjects (97.48%) than training subjects (88.13%) without discussion -> Added per-subject U-Net breakdown (Table 7), condition breakdown (Table 7b), and partition MAE; explained that `sub09`--`sub10` feature favorable lead coupling and less ectopic distortion; noted small test sample ($N=2$ subjects) requiring focus on 10-subject population mean ($90.76\%$) | `code/results/mega_benchmark_results.csv` groupby `sub_id` and `partition` |
| **S-03** | `build_full_report.py`, `mtr-8.tex` | Spatial PCA correlation was negative (-0.135) in Table 5 and "98.4% polarity" was unsupported -> Clarified mathematical sign ambiguity of eigenvector decomposition ($\mathbf{w} = \pm \mathbf{v}_2$); reported empirical raw signed correlation $-0.135$, positive fraction $41.2\%$, and mean magnitude $|\rho| = 0.513$; proved that Pan-Tompkins squaring $z[n] = y^2[n]$ makes beat detection and FHR invariant to sign | `diagnostics_mtr8_v2.py` evaluating 250 records in `mega_benchmark_results.csv` |
| **S-04** | `build_full_report.py`, `mtr-8.tex` | Population FHR MAE 6.57 bpm / 58.0% agreement appeared inconsistent with F1 93% and targets were shifted -> Added Table 7b breaking down performance across conditions: normal rhythm ($c0, c2, c3$) achieves MAE $2.99 - 3.29\,$bpm and agreement $74 - 82\%$; population MAE is driven by $c4$ (arrhythmia/extrasystoles, MAE $16.10\,$bpm, agreement $6.0\%$); restored clear clinical targets in Table 1 | Exact per-condition groupby in `mega_benchmark_results.csv` and `check_consistency.py` |
| **S-05** | `build_full_report.py`, `mtr-8.tex` | Sec. 9 statistical text cited stale CI numbers ($\pm 0.88\%$, $\pm 1.24\%$) and Sec. 10.1 / Sec. 15 R6 mislabeled all-subject means as test subjects -> Corrected Sec. 9 text to match Table 5 ($\text{SE} = 0.55\%$, half-width $\pm 1.08\%$ for PCA; $\text{SE} = 1.00\%$, half-width $\pm 1.97\%$ for U-Net); labeled 90.76% and 80.79% strictly as 10-subject population means, and 97.48% / 83.93% as held-out test generalization | Mathematical formula $\text{SE} = s / \sqrt{250}$, $\text{CI}_{95\%} = 1.96 \times \text{SE}$; Table 6 |
| **S-06** | `build_full_report.py`, `mtr-8.tex` | Database size stated as 5.10 GB at 4 bytes/sample with draft-residue 33.4 GB sentence -> Corrected arithmetic: $250 \times 75,000 \times 34 \times 4\text{ bytes} = 2.55\,$GB in 32-bit float ($1.28\,$GB in raw 16-bit WFDB format); partition sizes recomputed as Train $1.79\,$GB, Val $0.26\,$GB, Test $0.51\,$GB; deleted 33.4 GB tensor memory sentence | Byte calculation on disk and in memory; verified in `check_consistency.py` |
| **S-07** | `build_full_report.py`, `mtr-8.tex` | Overlap probability derivation mixed up $32.5\%$ and $12-18\%$ -> Derived exact distinct probabilities: fetal beat overlap probability $(w_m + w_f)/T_m = 140/800 = 17.5\%$; maternal beat overlap probability $(w_m + w_f)/T_f = 140/430 = 32.6\%$; complete fetal QRS containment $(w_m - w_f)/T_m = 40/800 = 5.0\%$ | Analytical probability formulations for $T_m=800\,$ms, $T_f=430\,$ms, $w_m=90\,$ms, $w_f=50\,$ms |
| **S-08** | `build_full_report.py`, `mtr-8.tex` | Amplitude ratio, dB, and FMR statements inconsistent -> Unified biophysical ranges: maternal peak $1.0 - 5.0\,$mV vs fetal $20 - 100\,\mu$V ($10 - 50\times$, $20 - 34\,$dB); RMS FMR range $0.20 - 0.54$, corresponding to $-14.0\,$dB to $-5.4\,$dB | Biophysical signal modeling; $20\log_{10}(0.20) = -14.0\,$dB, $20\log_{10}(0.54) = -5.4\,$dB |
| **S-09** | `build_full_report.py`, `mtr-8.tex` | Evaluation mode (calibration vs streaming) not explicitly partitioned -> Clarified two-phase architecture: Host PC computes covariance and eigen-weights during 3-s calibration buffer; Spartan-7 FPGA applies fixed weights sample-by-sample | System architecture specification in Section 5.1 |
| **S-10** | `build_full_report.py`, `mtr-8.tex` | Filter order (4th-order vs 2 SOS) and group delay (24 samples / 96 ms) conflicted -> Clarified: 4th-order bandpass design in Scipy yields 4 SOS biquads (8th-order total transfer function) with $>56\,$dB baseline attenuation at $0.1\,$Hz and $>18\,$dB at $60\,$Hz; group delay in physiological QRS band ($10-30\,$Hz) is $11.4 - 15.4\,$ms ($2.9 - 3.9$ samples), with $96\,$ms occurring only near the $0.5\,$Hz edge | `scipy.signal.sosfreqz` and `scipy.signal.group_delay` evaluation in `diagnostics_mtr8_v2.py` |
| **S-11** | `build_full_report.py`, `mtr-8.tex` | QRS detector spec incomplete and named "PPR-8" -> Fully specified Peak-Energy Fetal QRS Detector: 5-point Pan-Tompkins derivative, squaring, $W=15$ ($60\,$ms) integrator (optimized on training set for compact fetal QRS), dual adaptive thresholding ($SPKI, NPKI$), $200\,$ms blanking refractory period, $38\,$ms latency compensation; continuous online execution | Implementation in `fixed_point_model.py` and Pan-Tompkins (1985) |
| **S-12** | `build_full_report.py`, `mtr-8.tex` | Table 3 had 36 rows (duplicate Hankel-SVD V3 in TC3); M4-M9 undescribed; "Vivek Hybrid" used -> Removed duplicate V3 in TC3, standardizing Table 3 to exactly 35 rows (7 classical methods $\times$ 5 test cases); added concise descriptions for M4-M9; renamed to neutral "Wavelet-Threshold Hybrid" | Clean 35-row benchmark table; consistency verified in `check_consistency.py` |
| **S-13** | `build_full_report.py`, `mtr-8.tex` | Unsupported numbers quoted without evidence -> Removed or labeled literature-reported numbers (e.g. NLMS with thoracic reference in Table 9 R7); all reported empirical metrics tied directly to CSV logs | Direct CSV traceability |
| **S-15** | `build_full_report.py`, `mtr-8.tex` | Runtime numbers conflicted across figures and tables -> Unified units: reported both per 5-minute record ($75,000$ samples) and per 5-s processing window (PCA $190.7\,$ms / $3.2\,$ms; U-Net $98.6\,$ms / $1.6\,$ms; Hankel SVD $107.5\,$s / $1.79\,$s) | Profiling logs and `mega_benchmark_summary.csv` |
| **S-16** | `build_full_report.py`, `mtr-8.tex` | Limited test set size ($N=2$ subjects) -> Added Table 7 comparing Spatial PCA and Deep U-Net across all 10 subjects individually; explained sample size caveat in text | Per-subject CSV groupby |

---

## 2. Theory and Mathematics Items (T-01 to T-09)

| ID | File | Before -> After | Evidence |
|---|---|---|---|
| **T-01** | `build_full_report.py`, `mtr-8.tex` | Rank-3 maternal subspace vs $w = v_2$ heuristic -> Clarified: dominant maternal QRS energy is concentrated in $\mathbf{v}_1$ ($88.4\%$ variance); $\mathbf{w} = \mathbf{v}_2$ heuristic projects onto orthogonal subspace isolating the fetal dipole ($7.8\%$ variance) from residual noise ($\mathbf{v}_3, \mathbf{v}_4$); explained why 2 leads succeed on clean baseline ($95.3\%$) while 4 leads are required during 3D dipole axis variation in motion/contractions | Covariance eigen-decomposition and volume conduction theory |
| **T-03** | `build_full_report.py`, `mtr-8.tex` | "4 components capture 100.0% of signal space" tautology -> Replaced with meaningful metric: the first two principal components capture $96.2\%$ of total mixture variance ($\mathbf{v}_1 = 88.4\%, \mathbf{v}_2 = 7.8\%$), while residual components $\mathbf{v}_3$ ($2.6\%$) and $\mathbf{v}_4$ ($1.2\%$) contain noise | Eigenvalue spectrum calculation |
| **T-04** | `build_full_report.py`, `mtr-8.tex` | Problem statement promised unconstrained SINR maximization -> Re-framed objective: principal component spatial projection isolating fetal dipole while nulling dominant maternal subspace | Eigen-decomposition formulation in Section 3 and 5.1 |
| **T-06** | `build_full_report.py`, `mtr-8.tex` | Theoretical null depth evaluated to $93.3\,$dB -> Recomputed from Eq. (10): $R_{\text{null}} \approx 20\log_{10}(\sqrt{12}\cdot 2^{B-1}/\sqrt{C}) = 95.1\,$dB at $B=16, C=4$; added uniform quantization noise variance derivation; updated Fig. 5 with Eq. (10) theoretical curve | Closed-form evaluation in `check_consistency.py` |
| **T-07** | `build_full_report.py`, `mtr-8.tex` | Quantization model in Eq. (9) showed round-half-up and asymmetric clip -> Formulated with round-to-nearest-even: $x_q = \text{clip}(\text{round}(x \cdot 2^{15}), -32768, 32767) \cdot 2^{-15}$, matching `np.round` and DSP48E1 convergent rounding | Code inspection of `fixed_point_model.py` |

---

## 3. Figures and Visualizations (G-01 to G-16)

| ID | File | Before -> After | Evidence |
|---|---|---|---|
| **G-01** | `figures/signal_amplitude_disparity.png` | Nominal bars without measured ranges -> Rebuilt with peak disparity $10-50\times$ ($20-34\,$dB) and RMS FMR $-14.0$ to $-5.4\,$dB | Script `generate_all_audited_figures.py` |
| **G-03** | `figures/fmr_lead_topography_34ch.png` | 1-based vs 0-based index confusion -> Rebuilt with 0-based indices ($0-33$), annotating training partition (`sub01`--`sub07`), peak Lead 27 ($0.46$), and optimal sub-array $[27, 26, 28, 25]$ | Rebuilt from measured training FMR data |
| **G-04** | `figures/butterworth_sos_frequency_response.png` | Generic filter curves -> Rebuilt showing exact 4-SOS 8th-order 0.5--40 Hz bandpass response, 50/60 Hz notch filters, and passband group delay ($11.4-15.4\,$ms) | Scipy SOS filter evaluation |
| **G-05** | `figures/quantization_null_depth.png` | Plotted old $6.02B+1.76\,$dB bound -> Rebuilt with exact Eq. (10) null depth curve reaching $95.1\,$dB at $B=16$ | Rebuilt in `generate_all_audited_figures.py` |
| **G-06** | `build_full_report.py`, `mtr-8.tex` | Legends contained "Vivek Hybrid" -> Standardized to neutral "Wavelet-Threshold Hybrid" across all tables, captions, and text | Complete grep verification |
| **G-07** | `build_full_report.py`, `mtr-8.tex` | Fig. 7 caption said "six" architectures (legend had seven); U-Net in-sample -> Corrected count to seven architectures; marked U-Net as in-sample baseline on Subject 1 | Text and caption update |
| **G-08** | `build_full_report.py`, `mtr-8.tex` | Fig. 8 Bland-Altman caption lacked record specification -> Clarified: plotted on Subject 1 baseline records under noise (limits $[-6.75, +5.90]\,$bpm) | Caption update |
| **G-12** | `code/src/run_mega_benchmark.py`, `figures/mega_case_breakdown.png` | x-axis labeled $c2$ as "(Mod Noise)" -> Updated label to "$c2$ (HR Dynamics)" matching clinical definition | Fixed in benchmark plotting code |
| **G-15** | `build_full_report.py`, `mtr-8.tex` | Table 1 layout merged cold-start buffer; group delay mislabeled -> Separated rows cleanly; updated group delay to passband delay $11.4-15.4\,$ms with alarm target $\le 1.0\,$s | Table 1 redesign |

---

## 4. References and Compliance Items (R-01 to R-08, W-01 to W-04)

| ID | File | Before -> After | Evidence |
|---|---|---|---|
| **R-01** | `build_full_report.py`, `mtr-8.tex` | Andreotti et al. [17] bibliography author list incorrect -> Corrected: F. Andreotti, J. Behar, F. Zaunseder, J. Oster, and G. D. Clifford | Physiol. Meas. 2016 publication page |
| **R-02** | `build_full_report.py`, `mtr-8.tex` | Sameni et al. [13] citation clarification -> Cited Sameni et al. 2007 for Bayesian denoising, and Sameni & Clifford 2010 for 3D cardiac dipole model | Publication record |
| **R-05** | `build_full_report.py`, `mtr-8.tex` | EC57 cited for 50 ms fetal tolerance -> Corrected citation to PhysioNet/CinC Challenge 2013 standard (Silva et al. 2013) | Challenge 2013 scoring specifications |
| **R-06** | `build_full_report.py`, `mtr-8.tex` | Generic AI disclosure -> Expanded Section 19 with concrete attribution: Claude 3.5 Sonnet, GPT-4o, Antigravity; itemized code, math, and LaTeX assistance; confirmed human validation; added citations `\cite{anthropic2024,openai2024}` | Compliance with course guidelines |
| **R-07** | `build_full_report.py`, `mtr-8.tex` | Stale entries in Table 12 change register -> Updated R-08 to 128 clock cycles ($1.28\,\mu$s); R-09 to 1 BRAM; softened tone to transparent tool disclosure | Table 12 update |
| **W-01** | `build_full_report.py`, `mtr-8.tex` | Internal process wording ("Audited", "Reconciled") -> Replaced with objective engineering titles: "Empirical Performance Evaluation and Benchmark Analysis", "Subject 1 Stress Benchmark Performance Summary" | Professional report style |
| **W-02** | `build_full_report.py`, `mtr-8.tex` | Abstract too long without partition labels -> Shortened to ~200 words; added explicit partition labels next to every headline number | Abstract revision |
| **W-03** | `build_full_report.py`, `mtr-8.tex` | "Generalization" used for all-subject means -> Used "generalization" strictly for held-out test subjects (`sub09`--`sub10`); used "population mean" for 10-subject aggregates | Terminology alignment |
| **W-04** | `build_full_report.py`, `mtr-8.tex` | FPGA numbers described as physical achievements -> Clearly tagged as analytical architectural sizing ([L4 Target]) with hardware deployment scheduled for sprint | Engineering rigor audit |
