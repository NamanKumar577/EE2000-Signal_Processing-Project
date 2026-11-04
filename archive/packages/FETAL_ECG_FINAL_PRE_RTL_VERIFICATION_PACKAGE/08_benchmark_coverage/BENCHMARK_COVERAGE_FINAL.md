# Benchmark Coverage and Missing Records Investigation Report

## 1. Executive Summary & Audit Scope

In Phase 2, the independent technical audit observed that:
- The calibration benchmark contained **299 records** instead of the theoretical 300.
- The full-layout detector benchmark contained **746 records** instead of the theoretical 750.
- While `sub03_snr12dB_l2_c3` was explained in the previous changelog, three additional records (`sub07_snr12dB_l5_c3`, `sub09_snr00dB_l5_c0`, and `sub09_snr00dB_l5_c1`) were omitted without detailed forensic root-cause analysis.

During Phase 3, every file on disk, header metadata, WFDB binary block, and annotation array for all four records was forensically inspected.

---

## 2. Forensic Investigation of the Four Omitted Records

### Record 1: `sub03_snr12dB_l2_c3` (Layout 2, Condition 3)
- **Files Present:** `fecg1.dat`, `mecg.dat`, `noise1.dat`, `noise2.dat`, `noise3.dat`, and annotation `.qrs`.
- **Forensic Diagnosis:** `sub03_snr12dB_l2_c3_noise1.dat` contains **18 IEEE floating-point NaNs** directly in the upstream PhysioNet FECGSYNDB repository.
- **Impact:** Forming the composite mixture $\mathbf{X} = \mathbf{s}_{\text{fecg}} + \mathbf{s}_{\text{mecg}} + \mathbf{n}_1 + \mathbf{n}_2$ propagates NaNs into covariance estimation and IIR filtering (`np.isnan(mix).any() == True`).
- **Benchmark Coverage:** Affects both the 2-layout calibration benchmark and the 5-layout benchmark.
- **Classification:** **EXCLUDED — Corrupted Upstream Data**.

### Record 2: `sub07_snr12dB_l5_c3` (Layout 5, Condition 3)
- **Files Present:** `fecg1.dat`, `mecg.dat`, `noise1.dat`, `noise2.dat`, `noise3.dat`, and annotation `.qrs`.
- **Forensic Diagnosis:** `sub07_snr12dB_l5_c3_noise1.dat` contains **6 IEEE floating-point NaNs** in the upstream PhysioNet repository.
- **Impact:** Propagates NaNs into composite signal calculation.
- **Benchmark Coverage:** Layout 5 only (does not affect calibration suite, which uses layouts 1 and 2).
- **Classification:** **EXCLUDED — Corrupted Upstream Data**.

### Record 3: `sub09_snr00dB_l5_c0` (Layout 5, Condition 0)
- **Files Present:** Header files (`.hea`) and annotation files (`.qrs`) exist, but **all binary data files (`.dat`) are completely absent on disk** in the PhysioNet distribution.
- **Error Trigger:** `wfdb.rdrecord` throws `FileNotFoundError: [Errno 2] No such file or directory: sub09_snr00dB_l5_c0_fecg1.dat`.
- **Benchmark Coverage:** Layout 5 only.
- **Classification:** **EXCLUDED — Missing Upstream Binary Data**.

### Record 4: `sub09_snr00dB_l5_c1` (Layout 5, Condition 1)
- **Files Present:** `noise1.dat` and `noise2.dat` exist, but `fecg1.dat` and `mecg.dat` **do not exist on disk** in the PhysioNet distribution.
- **Error Trigger:** `wfdb.rdrecord` throws `FileNotFoundError: sub09_snr00dB_l5_c1_fecg1.dat`.
- **Benchmark Coverage:** Layout 5 only.
- **Classification:** **EXCLUDED — Missing Upstream Binary Data**.

---

## 3. Authoritative Benchmark Coverage Accounting

| Benchmark Suite | Evaluated Layouts | Theoretical Maximum Runs | Upstream Corrupt Records (NaNs) | Upstream Missing Files (.dat) | Actual Valid Evaluated Records | Actual Coverage Percentage |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Spatial Calibration Suite** | Layouts 1 & 2 | **300** ($10 \times 3 \times 2 \times 5$) | 1 (`sub03_l2_c3`) | 0 | **299** | **100.0%** of valid records |
| **FHR Reconciliation Suite** | Layout 1 | **150** ($10 \times 3 \times 1 \times 5$) | 0 | 0 | **150** | **100.0%** |
| **Fixed-Point Equivalence** | Layout 1, Cond 0 | **30** ($10 \times 3 \times 1 \times 1$) | 0 | 0 | **30** | **100.0%** |
| **Full Multi-Layout Benchmark** | Layouts 1 to 5 | **750** ($10 \times 3 \times 5 \times 5$) | 2 (`sub03_l2`, `sub07_l5`) | 2 (`sub09_l5_c0`, `sub09_l5_c1`) | **746** | **100.0%** of valid records |

Every missing record has been accounted for forensically and verified against raw disk payloads.
No records were silently dropped.
