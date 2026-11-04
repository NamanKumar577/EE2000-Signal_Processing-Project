# Final Algorithm Decision and Freeze Report

**Document ID:** `validation/pre_fpga/09_final_decisions/ALGORITHM_FREEZE_DECISION.md`  
**Decision Authority:** Senior Biomedical DSP Engineer, FPGA Architect, and Verification Lead  
**Governing Standard:** Empirical Pre-FPGA Validation Campaign (Tasks A through H)  

---

## 1. Executive Summary & Master Decision Dashboard

Following the rigorous completion of independent reproductions and empirical investigations, this document establishes the **formal algorithmic freeze decisions** for the Real-Time Multi-Channel Fetal ECG Extraction and Processing System. 

No component has been frozen arbitrarily. Every block has been classified based strictly on numerical evidence:

| Subsystem Block | Previous Proposed Baseline | Final Freeze Recommendation | Status Decision | Primary Empirical Evidence | Remaining Limitations / Action Required |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **1. Input Channels** | Lower Abdominal `[x27, x26, x28, x25]` | **Lower Abdominal `[x27, x26, x28, x25]`** | **KEEP** | Evaluated on 1,493 records across layouts `l1`–`l5`. Proved layout invariance ($77.78\%$ to $79.47\%$). | Dependent on correct electrode placement on maternal lower abdomen. |
| **2. Spatial Selection**| Fixed $\text{PC}_3$ Selection | **Envelope Autocorrelation (`autocorr`) with $[83, 136]$ sample window** | **MODIFY** | Lifted `sub08` from $66.18\%$ to **$82.10\%$** without ground truth; reduced maternal false lock to $1.0\%$. | Requires host PC to run FFT autocorrelation on initial 10s window. |
| **3. Calibration Confidence**| None (Always trust top candidate) | **Confidence Gate:** $\text{Conf} \ge 0.20$ and $R \ge 0.15$; Fallback to prior weights or default $\text{PC}_3$ | **MODIFY** | Flagged $100\%$ of ambiguous records in Task B, eliminating maternal false locks under high noise. | Default $\text{PC}_3$ fallback is suboptimal for `sub08`-type dipoles if initial boot fails. |
| **4. Recalibration Slew**| Instantaneous atomic weight switch | **64-Sample Linear Cross-Fade** ($256\text{ ms}$ ramp in hardware) | **MODIFY** | Eliminated up to $0.1178\text{ mV}$ baseline step discontinuities during eigenvector swaps in Task B. | Introduces a 256 ms smooth transition window during recalibration. |
| **5. HP1 Baseline Filter**| Shift-only $k=6$, 24-bit accumulator | **Shift-only $k=6$, 32-bit Accumulator** | **MODIFY** | Discovered $28\text{ bits}$ worst-case DC offset in Task E. Sizing accumulator to 32 bits prevents overflow. | Adds 8 bits to the LUT adder in module 6. |
| **6. LP40 Filter (FECG)**| 4th-order Butterworth $40\text{ Hz}$, $s24$ | **4th-order Butterworth $40\text{ Hz}$, $s24$** | **KEEP** | Delivers $71.88\text{ dB}$ SQNR with $10\text{ bits}$ internal accumulator headroom. | Causal IIR introduces $19.2\text{ ms}$ passband group delay. |
| **7. Detector Bandpass** | 4th-order Butterworth $8\text{--}30\text{ Hz}$ | **4th-order Butterworth $12\text{--}35\text{ Hz}$ (Config C)** | **MODIFY** | Slashed false alarms by $11,533$ beats; provides $-9.4\text{ dB}$ suppression against maternal T-waves. | S16 right-shift truncates lower bits on very weak signals ($<0.05\text{ mV}$). |
| **8. MWI Integration** | Trailing window $W=20\text{ samples}$ ($80\text{ ms}$) | **Trailing window $W=30\text{ samples}$ ($120\text{ ms}$, Config C)** | **MODIFY** | Bridges split biphasic R/S complexes into unimodal energy envelope, lifting PPV to $72.72\%$. | Increases MWI centroid group delay by $20.0\text{ ms}$ (compensated). |
| **9. Refractory Period**| $200\text{ ms}$ ($50\text{ samples}$) | **$200\text{ ms}$ ($50\text{ samples}$, Config C)** | **KEEP** | Retains lowest FHR MAE ($12.55\text{ bpm}$) and permits detection up to $300\text{ bpm}$ fetal tachycardia. | $220\text{ ms}$ was evaluated but rejected due to tachycardia clipping risk. |
| **10. Midpoint Beat Insertion**| Insert midpoint if $1.7 \le RR/RR_{prev} \le 2.3$ | **REJECT UN-GATED MIDPOINT INSERTION** | **REJECT** | Proven in Task C: **$73.5\%$ overall false insertion rate**, and **$99.4\%$ false insertions on decelerations ($c2$)**! Fabricates fake beats during fetal distress. | Midpoint split logic must never run in autonomous hardware. |
| **11. Interval Fusion** | Fuse beats if $RR < 60\text{ samples}$ | **Interval Fusion ($RR < 60\text{ samples}$ / $240\text{ ms}$)** | **KEEP** | Safely eliminates $17,079$ double-count false alarms without corrupting bradycardia. | Slightly delays reporting of fused beats by 1 cycle. |
| **12. FHR Post-Smoothing**| Causal Median5 filter | **Causal Median5 filter (`Median5`)** | **KEEP** | Slashes FHR MAE from $21.15\text{ bpm}$ to **$13.30\text{ bpm}$** (or $3.20\text{ bpm}$ on clean recordings). | Introduces 2 beats of group delay ($\approx 800\text{ ms}$). |
| **13. Real Clinical Trials**| Claiming FPGA clinical readiness | **Clinical Hospital Trials** | **NEEDS MORE DATA** | Real NIFEA records contain $50\text{ Hz}$ mains hum and lack public fetal ground truth. Clinical trials require prior ultrasound ground truth and hardware notch filter. | Cannot claim medical diagnostic readiness on real patients without ultrasound trial. |

---

## 2. Definitive Algorithmic Freeze Verdict

### **STATUS: ALGORITHM OFFICIALLY FROZEN FOR RTL DEVELOPMENT**
The mathematical processing chain, numerical wordlengths, filter coefficients, and telemetry protocols are **100% frozen** according to `FINAL_ALGORITHM_SPEC.md`. 

The engineering team is authorized to proceed with RTL authoring in Vivado for all 14 subsystem modules.
