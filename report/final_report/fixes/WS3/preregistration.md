# WS3 preregistration: replication tolerance and metrics (written before any new result was computed)

Date: 15 Nov 2026. This file is committed before running `tools/report_stats/replicate_behar.py`,
the R5 median or the R3 eigen-share script.

## Tolerance rule (all new replication rows)
A replication is **within tolerance** if our beat F1 is within **±5 points** of the published value,
computed with the **same statistic** (mean or median), the **same record set** and the **same
matching tolerance** as the paper. Rows without a published number on a comparable metric and data
set are QUALITATIVE ONLY. No per-row tolerance; no change after results are known.

## R-new-1: Behar et al. 2014 (Physiol. Meas. 35:1569), TS and TSpca on CinC 2013 set-a
- Records: set-a, the records the paper scores (68 records = 75 minus the 7 flagged: a33, a38, a47,
  a52, a54, a71, a74), unless the paper states a different set (then the paper's set, reported).
- Metric: beat F1 with ±50 ms matching tolerance, **mean over records** (as in the paper's table),
  published values TS 81.6 %, TSpca 86.1 %.
- Scoring window: whole 60-s record (the paper scores almost the whole minute); first and last
  beats within 50 ms of the record edges are kept as in a standard ±50 ms bipartite match.
- Implementation from the paper's description only (maternal QRS detection, maternal template
  built from aligned maternal beats; TS = mean template subtraction, TSpca = template from the
  first principal components of the aligned maternal cycles), followed by a fetal QRS detector
  on the residual. Labels used only for scoring.

## R5: fixed template subtraction on FECGSYNDB
- Statistic: **median** F1 over the 250 records of `code/results/mega_benchmark_results.csv`
  (method Template_Sub_Fixed), compared with the Andreotti et al. 2016 TS median 96.0 %;
  the mean (59.41 %) is kept as well.

## R3: 4-lead eigen-energy shares
- Covariance of leads [27, 26, 28, 25] of the mixture (fecg1 + mecg + noise1 + noise2) on
  sub01–sub07, snr12dB, l1, c0; share of variance of v1..v4 and share of the fetal component's
  energy captured by each eigenvector. Qualitative only (no published number on this data).
