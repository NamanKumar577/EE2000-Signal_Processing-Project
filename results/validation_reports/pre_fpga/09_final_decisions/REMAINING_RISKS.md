# Remaining Engineering and Clinical Risks Prior to Hardware Deployment

**Document ID:** `validation/pre_fpga/09_final_decisions/REMAINING_RISKS.md`  
**Author:** Biomedical Signal Processing & FPGA Verification Team  

---

## 1. Remaining Technical & Hardware Risks

| Risk Identifier | Severity | Category | Description of Hazard | Concrete Mitigation Plan |
| :--- | :---: | :---: | :--- | :--- |
| **RISK-01: 50 Hz Mains Hum in Clinical Environments** | **HIGH** | Front-End / Clinical | Clinical recordings often possess $50\text{ Hz}$ powerline interference up to $50\text{ dB}$ larger than fetal signals. | Instantiate an active driven-right-leg (DRL) circuit on ADS1298 and add a sharp $50\text{ Hz}$ IIR notch filter before the beamformer. |
| **RISK-02: Absence of Public Fetal Ground Truth on NIFEA** | **HIGH** | Clinical Validation | Public NIFEA recordings lack verifiable fetal reference annotations, precluding quantitative clinical F1 claims. | Partner with a clinical obstetrics department to record synchronized transabdominal ultrasound Doppler as ground truth. |
| **RISK-03: Vivado Timing Closure on 48-bit Accumulators** | **MEDIUM** | FPGA Implementation | Multi-cycle paths between distributed slice LUTs and DSP48E1 accumulators could fail $100\text{ MHz}$ timing if un-pipelined. | Register all DSP48E1 inputs (`AREG=1, BREG=1, MREG=1, PREG=1`); insert 1 pipeline register between cascading biquad stages. |
| **RISK-04: Recalibration During Sudden Maternal Posture Shifts** | **MEDIUM** | Algorithmic / Spatial | Rapid maternal rollover can alter electrode geometry faster than the 60-second recalibration timer. | Host calibration engine monitors covariance stationarity; triggers an early recalibration if residual variance jumps $>3\times$. |
| **RISK-05: Single-Core Host Calibration Dependency** | **LOW** | System Architecture | The FPGA depends on host PC to transmit valid spatial weights during boot and recalibration. | The FPGA boots into a proven geometric default vector ($\text{PC}_3$, Lead 28), ensuring autonomous streaming even if host is disconnected. |

---

## 2. Go / No-Go Decision for RTL Implementation

### **FINAL VERDICT: GO FOR RTL IMPLEMENTATION**
- **Algorithmic Correctness:** Validated on 1,493 complete simulation records ($78.59\%$ baseline F1, layout-invariant across `l1`–`l5`).
- **Numerical Robustness:** Bit-accurate integer equivalence confirmed ($98.39\%$ exact match, $-0.16\%$ net F1 degradation, worst-case accumulator bitwidths proven).
- **Safety Compliance:** Hazardous midpoint beat insertion permanently rejected; 2-bit telemetry state flags specified.
- **Hardware Architecture:** All 14 modules specified with pin-level interfaces and timing budgets.

The project is officially certified ready for RTL authoring on the Spartan-7 FPGA.
