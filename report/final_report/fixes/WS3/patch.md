# WS3 patch (applied by fixes/WS3/apply.py; replacement text is the NEW string in apply.py)

Preregistration committed first: `report/final_report/fixes/WS3/preregistration.md`, commit 6e5e0cd
(±5 points, same statistic, same records, ±50 ms; written before any new result was computed).

Apply with: `venv/Scripts/python.exe report/final_report/fixes/WS3/apply.py` (replaces the Sec. 13 text
block and Tab. replication_scorecard; appends bibitem `behar2013cinc` before `\end{thebibliography}`).

## Results (all from files)
| Item | Value | Source |
|---|---|---|
| R8 TS, 68 records, mean / median / pooled F1 | 63.88 / 89.30 / 68.53 % | tools/report_stats/out/behar_replication_summary.csv |
| R8 TSpca, 68 records, mean / median / pooled | 67.78 / 89.79 / 70.60 % | same |
| R8 records < 50 % (TS / TSpca) | 27 / 24 of 68; records ≥ 50 % average 93.8 / 91.0 % | behar_replication_per_record.csv |
| Published (Behar, Oster, Clifford, CinC 2013, Tab. 2, F1-10Hz) | TS 81.6 %, TSpca 86.0 % | full text read (PhysioNet PDF) |
| v7-DL on the same 68 records | 84.0 % | report/v61_v7/board_v7/board_cdev_ad_ctest_syn.csv |
| R5 Template_Sub_Fixed, 250 records | mean 59.41 %, median 61.30 % | tools/report_stats/out/r5_median.csv |
| R3 variance share v1..v4 (sub01-07 mean) | 94.0 / 5.3 / 0.7 / 0.0 % | tools/report_stats/out/r3_eigen.csv |
| R3 fetal energy share v1..v4 | 70.7 / 25.6 / 3.6 / 0.0 % | same |

Verdicts: R8 FAIL (both), R5 FAIL (median now same statistic), R3 qualitative and contradicts the
mid-term "fetal dipole isolated in v2" claim (also stated in the appendix A.4.1 text and the mid-term
Fig. eigen_spectrum caption: WS4 should fix those with these numbers).
New summary: 0 of 8 within tolerance, 0 explained, 2 outside (R5, R8), 5 qualitative, 1 not run.

## Cause analysis (R8)
Bimodal outcome: median ~89–90 % and 91–94 % on the records that work, but 24–27 of 68 records
below 50 %. The paper does not give the detector bands, thresholds, cycle window or template scaling;
our choices (5–15 Hz maternal / 10–45 Hz fetal energy detectors, 0.3 × 99th-percentile threshold,
−250..+450 ms cycle window, least-squares template scaling, lowest-SMI channel) cause whole-record
failures. No tuning was done after the first run (preregistration). R8 therefore does not test the
published values; it shows our implementation of the description does not reach them.

## Reference
- New: `behar2013cinc` — J. Behar, J. Oster, G. D. Clifford, "Non-Invasive FECG Extraction from a Set of
  Abdominal Sensors", Computing in Cardiology 2013; 40:297–300. Verified from the full text (PhysioNet
  challenge paper 0297.pdf: title, authors, volume, pages, Tables 1–2). DOI not checked (Xplore not accessed).
- Existing `behar2014b` (Physiol. Meas. 35:1569, DOI 10.1088/0967-3334/35/8/1569): only abstract-level
  metadata confirmed via search; the full text was not accessible (HAL blocks bots). The literature
  table quotes TSpca 86.1 % from behar2014b; the CinC 2013 paper gives 86.0 %. Could not check which the
  2014 paper reports — flag for WS2/WS6 (keep 86.1 only if someone checks the 2014 table).

## Register rows (for Table 23)
- C: Tab. replication_scorecard R3 — old: "not measured (typed-in values)"; new: variance 94.0/5.3/0.7/0.0 %, fetal 70.7 % in v1, 25.6 % in v2; Sec. 13; computed from FECGSYNDB components (r3_eigen.py).
- C: R5 — old: mean 59.4 % only; new: median 61.3 % (mean 59.4 %), same statistic as the published median; Sec. 13; r5_median.csv.
- C: Sec. 13 summary — old: 0 of 7 within tolerance, 1 outside; new: 0 of 8, 2 outside (R5, R8); Sec. 13; new row R8.
- F: New replication R8 (Behar TS/TSpca on CinC set-a), preregistered tolerance ±5 points (commit 6e5e0cd); Sec. 13.

## Not done
- No tuning of R8 after seeing results (by design of the preregistration).
- The 2014 Physiol. Meas. paper's own tables could not be read (access blocked).
