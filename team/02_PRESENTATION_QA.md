# Likely presentation / viva questions with short answers

All numbers are board results of the final design **v7-DL** unless another version is named. Sources:
- `report/v61_v7/LOG.md`;
- `report/final_report/fpr-8.tex`;
- the board CSVs in `report/v61_v7/board_*`.

The cheat sheet is `03_KEY_NUMBERS.md`.

How to answer:
1. Say the number.
2. Say where it comes from (board or C model, dev or test).
3. Admit limits openly.

Examiners like "we measured X, we did not measure Y".

---

## A. Problem and physiology

**Q1. What problem do you solve, in one sentence?**
We find the fetal heartbeats and the fetal heart rate (FHR) from 4 electrodes on the mother's abdomen, in real time, on a Spartan-7 FPGA. The hard part is that the fetal ECG is about 10–250× weaker than the mother's ECG (about 20–100 µV against 1–5 mV) and uses the same frequency band (0.5–40 Hz).
*Key number:* 4 leads, 250 Hz, fetal ECG up to 250× weaker.

**Q2. Why can't you just filter the mother out?**
The maternal and fetal QRS complexes share the same frequency band, so a frequency filter would remove both. We work in space and time instead:
- the maternal beat is cancelled lead by lead with a template of the last 20 maternal beats;
- spatial filters across the 4 leads make the fetal beat stand out.

Even a perfect, label-based single spatial filter reaches only about 60% on CinC, which is why we keep several candidate tracks.
*Key number:* best possible single 4-lead linear filter: about 60% on CinC.

**Q3. What exactly does the system output?**
For every fetal beat, the board outputs:
- the beat time (sample number at 250 Hz);
- the FHR in 0.1 bpm;
- the track it came from (0–15, or 16 = a missed beat filled in by the clean-up).

The live output computes FHR = 60·250 / median of the last 5 RR intervals. The final v7 output uses a centred median of 5 intervals.
*Key number:* final beats are OUT7 frames (0x8D), about 13.5 s after the beat.

**Q4. Why non-invasive, and why does FHR matter?**
FHR is the main sign used to check fetal well-being in pregnancy and labour. A scalp electrode gives a clean fetal ECG, but it is invasive and only possible during labour. Abdominal electrodes are non-invasive and still give the timing of every single beat.
*Key number:* ADFECGDB has both, abdominal leads plus a scalp reference; we reach 96.1% there.

---

## B. Data sets and scoring

**Q5. Which data did you use?**
- **FECGSYNDB:** synthetic, 1,248 usable 5-min records (10 subjects × 5 SNRs × 5 conditions × 5 repetitions).
- **PhysioNet/CinC 2013 set-a:** 75 real 60-s records, 4 leads at 1 kHz.
- **ADFECGDB:** 5 real 5-min records with a scalp-electrode reference.

CinC is split by record number: odd = dev (38), even = held-out test (37).
*Key number:* 140 records on the board (60 synthetic + 38 + 37 + 5).

**Q6. How do you score?**
- **Beat F1** = 2·Se·PPV/(Se+PPV). A detected beat counts if it is within ±50 ms (13 samples) of a reference beat.
- Scoring runs from **20 s** to the end of the record.
- **FHR MAE** compares our FHR, 0.5 s after each true beat, with the reference FHR. No output counts as a full error.

*Key number:* ±50 ms, from 20 s.

**Q7. Isn't starting at 20 s cheating?**
No. The design needs the first ~20 s to learn the mother (10 s) and calibrate the spatial filters (up to 15 s). The first beat comes out at about 19.5 s. The same rule is used for every version, and the web demo shows the warm-up openly.
*Key number:* first live beat at about 19.5 s.

**Q8. Did you tune on the test set?** *(tricky)*
No design decision used the CinC test half.
- **Dev data:** CinC dev, ADFECGDB and a 60-record FECGSYNDB subset (every 21st record).
- **Test data:** each frozen design was scored once on CinC test.

Honest caveat: the same test half had already been scored for v5 and v6, and it has now been scored once each for v5, v6, v6.1, v7-LA and v7-DL. So it is not a fresh test set; a new claim would need fresh data. ADFECGDB has been a dev set since v4.
*Key number:* CinC test = 37 records, scored once per frozen design.

**Q9. Why is CinC so much lower than synthetic?** *(tricky)*
- **Synthetic data is easier.** It comes from a model with clean geometry. Real CinC records are only 60 s long, so only 40 s are scored. Electrode placement and noise vary, and the fetal signal can be very weak.
- **Some references are wrong.** The challenge marks 7 of the 75 references as unreliable, e.g. a54 shows a flat 100 bpm after 27 s.
- **Where the failures are.** 15 of the 75 CinC records are below 70%:
  - 5 have unreliable references;
  - 8 have no candidate track above 70% (best 42–69%);
  - 2 have a best track of only 71–73%;
  - none had a good track (≥ 85%) that we failed to pick.

So the remaining loss is in the front end and the candidates, not in the choice.
*Key number:* all 75 CinC: final 80.8% vs best single track 82.1%. CinC test on reliable references only: 82.0%. Synthetic: 93.7%.

**Q10. How sure are you of these numbers? The test set is small.**
We give 95% bootstrap confidence intervals over records. CinC test for v7-DL is 76.9% [68.3, 84.7], so about ±8 points. Part of the dev/test gap (84.7 vs 76.9) is chance: the dev half was also easier for older versions (mid-term 22.8 vs 16.7). The other part comes from choosing the design on dev.
*Key number:* CinC test 76.9 [68.3, 84.7].

---

## C. Algorithm

**Q11. Explain the algorithm in one minute.**
Per 250 Hz sample, on 4 leads:
1. Filters.
2. Maternal R-peak detection on PCA projections (PCA learned from the first 10 s).
3. Per-lead maternal ECG cancellation with a template from the last 20 maternal beats.
4. 16 candidate fetal signals from self-calibrated GEVD spatial filters.
5. RR-predictive beat trackers.
6. A label-free choice of the best track every 2.5 s.
7. Beats and FHR.

v7 adds an FPGA look-ahead unit that chooses the track again with about 7.5 s of future data and cleans up the beats.
*Key number:* 16 candidate tracks, a decision every 2.5 s.

**Q12. What is GEVD and why 16 tracks?**
GEVD (generalised eigen-decomposition) finds spatial filters w that maximise w'Aw / w'Bw:
- A = covariance around the design's own detected beats ("self-referencing", no labels);
- B = total covariance.

This makes the fetal QRS stand out. One filter is not robust on real data, so the PC computes 16, the FPGA runs all 16 tracks in parallel, and the selector picks one. From v6.1 on, the filters are recalibrated every 30 s.
*Key number:* first calibration on [3, 15) s; first selected beat at about 19.5 s.

**Q13. How does the maternal cancellation work?**
1. The FPGA detects maternal R peaks on 4 PCA projections of the leads.
2. The PC picks the best maternal train every 5 s.
3. For each maternal beat, the PC sends a template basis: mean + 2 principal components of the last 20 beat segments.
4. Lead by lead, the FPGA finds the best lag, projects the beat on the basis and subtracts it.

*Key number:* template from the last 20 maternal beats.

**Q14. How is the track chosen in the live (causal) output?**
Every 2.5 s each track gets a label-free quality score from:
- beat-shape consistency;
- tracker acceptance;
- prominence;
- RR regularity;
- agreement with the other tracks;
- a mild FHR prior.

A penalty applies if the track's beats coincide with maternal R peaks. It is used only when the maternal train holds at least 10% of the maternal-band energy; otherwise the "mother" may really be the fetus.
*Key number:* the 10% energy gate took the FECGSYNDB subset from 78.4% to 93.8% (v7-LA dev).

**Q15. What do "causal" and "label-free" mean, and why insist on them?**
- **Causal:** every decision at sample n uses only samples up to n, as in a real device.
- **Label-free:** reference annotations are used only by the scoring script, never by the algorithm.

The mid-term design scored 93.0% in batch mode. Run causally, it gave 82.2% on synthetic and only 16.7% on real held-out CinC. Since then we judge only causal results on real held-out data.
*Key number:* 93.0 → 82.2 → 16.7%.

**Q16. What happens on an ectopic beat?** *(tricky)*
An early (ectopic) beat falls outside the tracker's predicted window, and the RR-regularity score treats the early beat and the following pause as errors. As a result:
- the beat may be missed;
- the clean-up may drop it as a "split" beat, or fill an extra beat into the pause.

The 5-interval median stops one odd beat from moving the FHR much. We do not detect or flag arrhythmias. The look-ahead helped a lot here, but ectopic beats are still the weakest synthetic condition.
*Key number:* FECGSYNDB c4 (ectopic beats): v6.1 77.9 → v7-DL 84.0%; the other conditions score 91.9–98.0%.

**Q17. What about fetal bradycardia or twins?**
The mild FHR prior rises from 0.2 at 80 bpm to 1 at ≥ 120 bpm, so a true FHR below about 110 bpm can be under-selected. We kept the prior mild on purpose: a stronger one gave only +0.4 on CinC dev and was rejected. Twins are not covered.
*Key number:* prior 0.2 at 80 bpm → 1 at 120 bpm.

---

## D. Why not deep learning

**Q18. Why didn't you use deep learning?**
We tried it at mid-term: a 1D U-Net with 1.42 M parameters.
- It scored 90.0% on a 179-record synthetic subset but only **17.7%** on the real ADFECGDB. Changing lead polarity or scaling did not help.
- We have too few labelled real recordings to train on and still keep an honest held-out test.
- It would not fit on chip: 1.42 M weights at 8 bit are about 1.4 MB, while the whole XC7S50 has about 0.34 MB of block RAM (75 × 36 Kb).

In the final phase we also tried a small logistic track selector trained on 120 synthetic records. It lost 0.5 points on CinC dev, the same lesson again. A classical pipeline is explainable and can be checked byte by byte.
*Key number:* U-Net 90.0% synthetic → 17.7% real.

---

## E. Hardware and RTL

**Q19. What runs on the FPGA and what on the PC?**
The FPGA does **all** sample-rate work in hand-written Verilog, with no soft processor:
- filters;
- maternal detection and cancellation;
- 16 projections;
- trackers and features;
- output beats and FHR;
- in v7, the look-ahead unit and the display driver.

The PC "brain" answers 5 low-rate requests:
- maternal PCA (once, at 10 s);
- maternal train choice (every 5 s);
- template basis (per maternal beat);
- GEVD calibration (at 15 s, then every 30 s);
- track selection (every 2.5 s).

*Key number:* 5 PC decisions; the look-ahead runs on the FPGA, not on the PC.

**Q20. Why does the PC still exist?** *(tricky)*
The 5 decisions need floating-point eigen-decompositions (PCA, GEVD). They are needed only per beat or every few seconds, so eigen-solvers in RTL would cost a lot of area for no speed gain.
- The PC never receives the raw recording stream. It gets compact data from the FPGA:
  - a 4×4 covariance;
  - maternal peaks and beat segments;
  - a 12-s block of filtered data for calibration;
  - track features.
- The FPGA waits for each answer, so results do not depend on link timing and stay bit-exact.
- The PC also streams the recording, because we have no electrode front end.

A stand-alone device would need a small processor or more RTL for the eigen-solvers.
*Key number:* v7's look-ahead added zero PC work.

**Q21. Why hand-written RTL instead of the MicroBlaze version (v5)?**
v5 ran the whole algorithm as C on a MicroBlaze soft CPU in the FPGA (3.3k LUTs, CinC test 65.8%). For v6 we wanted the signal processing to be our own datapath. The RTL alone needs a median of 1,485 clock cycles per sample: about 30 µs of a 4-ms sample period, or about 140× faster than real time. The price is about 5× the LUTs of the MicroBlaze version.
*Key number:* 1,485 cycles/sample, about 140× real time (RTL alone).

**Q22. Which number formats did you use?**
- Raw input: int16.
- Filter data: Q8 in int32.
- SOS coefficients: Q28.
- Products and accumulators: 64-bit.
- Spatial weights and maternal projections: Q14.
- Template basis: s24 Q22.
- Envelopes: 16-bit codes with 8 significant bits.

The C model uses exactly the same integer arithmetic. That is what makes byte-for-byte comparison possible.
*Key number:* Q28 coefficients, 64-bit accumulators.

**Q23. How do PC and board talk?**
- **Link:** UART at 921,600 baud.
- **Frames:** `A5 5A cmd len16 payload xor8`.
- **Samples:** sent in 64-sample frames (0.256 s of signal); the PC waits for DONE after each.
- **Requests:** the FPGA sends requests (e.g. REQ_CAL), the PC sends responses.
- **v7 additions:** FLUSH (0x03, PC → board) at the end of a recording; OUT7 (0x8D, final beats) and END7 (0x8E, count) back.

*Key number:* 921,600 baud, 64-sample frames.

**Q24. Why 82% LUTs?** *(tricky)*
v6.1 used 58%; the v7 look-ahead and display units added 7.7k LUTs and 11 BRAM tiles. The look-ahead unit must:
- keep recent beats and beat-shape sums for all 16 tracks;
- score tracks in log2;
- run a Viterbi step;
- clean up beats.

Its first RTL version used 13.2k LUTs alone, and the design did not fit (101%). Because the unit runs only once per 2.5 s, we made shifts, divisions and log2 one bit per cycle and used single-port small memories. That cut it to 8.4k LUTs with identical output. 82% is fine for this design, but it leaves little room for more logic.
*Key number:* 26,701 LUTs (81.9%), 71/75 BRAM, 43 DSP.

**Q25. Timing slack is only +0.05 ns. Is that a problem?**
No: timing is met at 50 MHz ("All user specified timing constraints are met"), and hold slack is positive too. The margin is small, so more logic would need pipelining or a lower clock.
*Key number:* WNS +0.048 ns at 50 MHz (v6.1: +0.41 ns).

**Q26. How much power?**
Vivado's estimate for the routed v7 design is 0.445 W on-chip (0.369 W dynamic + 0.076 W static), with default switching activity. We did not measure the board's power.
*Key number:* 0.445 W (estimate only).

**Q27. How fast is the whole system?**
On the board it runs 4.0–4.5× faster than real time. The limit is the UART round trips and the PC answers, not the FPGA logic. A 60-s CinC record takes about 13 s; a 5-min synthetic record takes about 74 s. The web demo deliberately streams at true speed.
*Key number:* 4.0–4.5× real time (board); about 140× (RTL alone).

**Q28. Is there a real analogue front end or ADC?**
No. Recordings are streamed from files over the UART; we built no electrodes, amplifier or ADC. In a real device an ADC would feed the same RTL, but we have not shown that.
*Key number:* —

---

## F. Verification

**Q29. How did you verify the hardware? How did you debug it?**
1. **C model first.** A bit-accurate integer C model is the specification.
2. **RTL simulation.** An xsim system testbench streams a recording like the PC does and checks every byte the RTL sends against the model. For v7 that was 9 records with 0 byte errors, including FLUSH and END7.
3. **Board.** The board's complete output stream was compared with the model: 140/140 records bit-exact for v6, v6.1 and v7-DL.

We always changed the model first, then the RTL. A bug then shows up as "the first differing byte", which points straight to the frame and the unit.
*Key number:* 140/140 bit-exact; 207,603,379 uplink bytes for v7.

**Q30. What does bit-exact prove, and what does it not prove?** *(tricky)*
It **proves** that the hardware computes exactly what the C model computes, byte for byte, including every PC request, on those 140 records and 9 simulated ones. So:
- there are no RTL or synthesis bugs on these inputs;
- accuracy measured with the model is the accuracy of the hardware.

It does **not** prove:
- that the algorithm is good (F1 measures that);
- that the model has no design mistake;
- correctness on inputs we never ran;
- anything about real electrodes or analogue noise;
- clinical validity.

Timing safety comes from static timing analysis, not from bit-exactness.
*Key number:* 140/140 records, 3 designs.

**Q31. What do your tests cover?**
The suite result is **270 passed, 3 skipped**. The 3 skipped tests are slow Vivado RTL simulations, run with `RUN_RTL=1`. The system tests check:
- the model matches the board (MD5) on saved records;
- causality: cutting a recording short never changes output already produced;
- determinism;
- robustness to inverted polarity, halved gain and a dead lead;
- for v7: the v6.1 stream is untouched, END7 equals the number of OUT7 frames, the delay is ≤ 17.5 s, and an ADFECGDB accuracy guard holds.

*Key number:* 270 passed, 3 skipped.

---

## G. Results

**Q32. What are your headline results?**
v7-DL on the board, beat F1:

| Data set | F1 |
|---|---|
| CinC test (held out) | 76.9% |
| CinC dev | 84.7% |
| ADFECGDB | 96.1% |
| FECGSYNDB subset | 93.4% |
| all 1,248 FECGSYNDB (C model) | 93.7% |

Every board record is bit-exact.
*Key number:* CinC test 16.7% (mid-term) → 65.5% (v6) → 71.9% (v6.1) → **76.9% (v7-DL)**.

**Q33. Where is the remaining error?**
On all 75 CinC records the final output scores 80.8%. The best single candidate track, picked with labels, would score 82.1%, so the choice of track is no longer the main loss. Most of the 15 records below 70% have no good candidate at all, or unreliable references. The next gain must come from better candidates: the front end and the spatial filters.
*Key number:* 80.8% vs 82.1%.

**Q34. Why is the FHR error on CinC test slightly worse with v7 (11.53 vs 11.16 bpm)?**
The difference is small, and we have not analysed its cause record by record. On the same test set, F1 improved by more than 1 point on 33 of 37 records and got worse on only 1. The FHR error improved on CinC dev (8.91 → 6.45 bpm) and on synthetic (4.85 → 3.98 bpm). It got slightly worse on CinC test and on ADFECGDB (1.72 → 2.13 bpm).
*Key number:* FHR MAE on CinC test 11.53 bpm.

**Q35. v7-DL matches or beats the offline v7-LA on real data. How, if LA sees the whole recording?**
The two differ in details:
- v7-DL uses integer scores, a slightly different shape measure and a 15-s deadline;
- v7-LA uses a centred ±15-s float window.

The differences are far inside the ±8-point confidence intervals, so we treat them as equal.
*Key number:* CinC test DL 76.9 vs LA 75.6; all synthetic DL 93.7 vs LA 94.3.

---

## H. v6.1

**Q36. What changed in v6.1 and why?**
Two label-free, causal fixes.

1. **Robust maternal detector.** In 4 of 5 CinC failures where no mother was found, all 4 maternal detectors fired zero times: one early transient had set a threshold that was never crossed again. Fix: the warm-up starts at sample 256, and the peak level decays (by 1/8 steps) after 2 s without a detection. Example: a73 now finds the mother at 96 bpm.
2. **Recalibration every 30 s.** The FPGA sends back the last 12 s, the PC keeps a track's old filter unless the new one is better, and the FPGA cross-fades over 64 samples.

*Key number:* CinC test 65.5 → 71.9%; CinC dev 76.0 → 80.4%.

**Q37. What did you try that did not work?**
"Smarter selection" rules: a maternal-rate penalty, rate voting, FHR continuity, and other windows and weights. The best one gained +0.5 on CinC dev but lost 0.6–1.4 on synthetic, and the learned selector lost 0.5, so we kept the v6 selector. Even with fix 1, the causal choice still lost about 5 points to the best single track (79.5 vs 84.7 on CinC dev). That gap is what led us to the look-ahead.
*Key number:* causal choice 79.5 vs best track 84.7 (CinC dev).

---

## I. v7 look-ahead and delay

**Q38. How does the v7 look-ahead work?**
A new RTL unit, `v7_la`, only listens to the other units, so the live v6.1 output stays untouched. Every 2.5 s of signal it:
1. scores all 16 tracks over a window from 15 s before to 7.5 s after the segment;
2. runs one Viterbi step, which picks the best track path with a cost for switching tracks;
3. cleans up the beats: fills one missed beat, drops a beat that splits an interval;
4. sends the final beats with a centred FHR as OUT7 frames.

At the end of a recording the PC sends FLUSH (0x03). The board finishes the last segments with the data it has and sends END7 (0x8E) with the number of final beats. In the web demo this is the "FLUSH sent" line at 60 s.
*Key number:* median delay 13.5 s, max 17.5 s; a01 gives 102 final beats, F1 98.0%.

**Q39. Is it real time if the output is 15 s late?** *(tricky)*
Yes, in the throughput sense: the board keeps up with the input (4–4.5× faster than real time, and the demo streams at true speed). The latency is a design choice, and the board gives both outputs at once:
- **live output:** each beat 1.5–2 s after it happens;
- **final output:** 13.5 s (median) after it happens, at most 17.5 s, and about 5 points better on held-out CinC.

For an FHR trend display a ~15-s delay is acceptable. Neither output is fast enough for beat-synchronous triggering.
*Key number:* live 1.5–2 s; final 13.5 s median / 17.5 s max.

**Q40. Is v7 still causal?** *(tricky)*
The system is causal with a fixed delay. Everything it outputs at time T depends only on input up to T; our tests check that cutting the input short never changes output already sent. The final decision about a beat does use up to about 10 s of signal after that beat. In that sense it is a delayed decision, like any filter with group delay. v7-LA on the PC is not causal: it needs the whole recording.
*Key number:* future window = 3 segments of 2.5 s (7.5 s) + 1.5 s margin.

**Q41. Why 13.5 s? Could it be shorter?**
We chose the delay on dev sets only:
- 3 future segments and decision lag 0 gave CinC dev 84.7 with a 13.5-s median delay;
- 1 more segment of lag and 2 clean-up passes gained ≤ 0.2 points, but the median delay rose to 17.9 s;
- the 15-s deadline caps the delay at 17.5 s without changing F1.

A shorter window is possible but trades accuracy for delay. We did not build a shorter window on the FPGA.
*Key number:* 13.5 s median buys +4.3 points on CinC dev (80.4 → 84.7).

---

## J. Limitations and next steps

**Q42. What are the main limitations?**
- Real-data F1 of 76.9% (82.0% on reliable references) is not clinical grade.
- The real test sets are small and reused (37 CinC records of 60 s, 5 ADFECGDB records).
- The final output is ~13.5 s late.
- Ectopic beats (84.0%), possible bradycardia under-selection and twins are not handled.
- A PC is still in the loop.
- The timing margin is small.
- There is no analogue front end, and board power was not measured.

*Key number:* CinC test 76.9%.

**Q43. What would you do next?**
1. Better candidates: improve the front end and the spatial filters, since that is where the remaining real-data error is.
2. Test on a fresh, untouched real data set.
3. Move the eigen-solvers onto the board (small CPU or RTL) for a stand-alone device.
4. Add a real electrode, amplifier and ADC front end, and measure power.

*Key number:* 8 of the 15 failing CinC records have no candidate track above 70%.

---

## K. Use of AI

**Q44. Did you use AI tools? How do you know the code is right?**
Yes, and the report says so.
- **Mid-term:** Claude 3.5 Sonnet, ChatGPT (GPT-4o) and Gemini/Antigravity.
- **Final phase:** mainly Claude Code as a programming aid for the Python scripts, the C model, the Verilog, plots and documentation; Antigravity once, for a code audit.
- **What we decided:** the goals and rules (strictly causal, no labels, a held-out real test set, all sample-rate work in the FPGA).
- **Disclosure:** all prompts are in `AI_PROMPTS.md` in the submission, as the course requires.

We did not trust the code; we checked it:
- every result was checked against the saved result files;
- the RTL is compared byte for byte with the C model in simulation and on the board;
- the test suite runs on every change;
- each of us can explain our own part.

*Key number:* 140/140 bit-exact; 270 tests passing.

---

## L. Teamwork

**Q45. Who did what?**

| Member | Part |
|---|---|
| **Naman** | data and integration: data set preparation, test cases and test suite, live web demo, report assembly; SVD methods at mid-term |
| **Vivek** | fixed-point design and first full FPGA version: fixed-point model, UART bring-up and message protocol, v5 on MicroBlaze, board evaluation script with the bit-exact check; wavelet-threshold and SVD-template methods at mid-term |
| **Anshu** | real-time algorithm and accuracy: causal label-free algorithm v2–v5, CinC dev/test protocol and scoring, U-Net baseline; template subtraction and multichannel study at mid-term |
| **Astitva** | final hardware (v6 RTL): hardware/PC split, bit-accurate C model, hand-written Verilog, testbenches, board verification, BRAM optimisation; SWT-LMS-SSNF method at mid-term |

Biggest shared lesson:
- Judge a design on causal processing and real held-out data. The mid-term design went from 93.0% on synthetic data to 16.7% on real data.
- Write a bit-exact model before the hardware.

*Key number:* —
