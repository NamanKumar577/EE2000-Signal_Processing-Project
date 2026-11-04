# Documentation, FPGA and Configuration Audit Report

**Project:** Multichannel Fetal ECG Extraction & Spartan-7 FPGA Implementation (EE2000 Paper ID: 0008)  
**Date:** 2026-11-03  
**Auditor:** Teamwork Documentation & FPGA Audit Coordinator  
**Target Scope:** 15 root Markdown documents, `docs/archive/`, `papers/`, `page/`, package specifications, and configuration files.

---

## 1. Executive Summary

The repository contains an extraordinarily rich set of technical documentation, hardware sizing specifications, literature reviews, and team tracking logs. However, **15 lengthy Markdown documents currently reside in the repository root directory**, alongside 4 PDF documents, 4 ZIP archives, and transient log files. This root clutter obscures the entry points for new engineers and tooling.

This audit categorizes all documentation, identifies authoritative versus superseded specifications, catalogs reference literature, and highlights critical configuration files that must be protected.

---

## 2. Categorization of Documentation

### A. Authoritative FPGA Hardware Specifications
- **`FPGA_SPEC.md` (Authoritative — v0.2 Frozen Spec):**
  - Complete architectural specification for the AMD/Xilinx Spartan-7 `XC7S50-1CSGA324C` FPGA on the RealDigital Boolean Board.
  - Specifies: 4-channel $250\,$Hz streaming input, 16-bit Q1.14 fixed-point representation, $N=750$ sample trailing covariance buffer ($3.0\,$s), 4-iteration power iteration, Pan-Tompkins integer datapath, and 921,600 baud UART telemetry.
- **`DATASHEETS_AND_HARDWARE_SPECS.md` (Authoritative Hardware Reference):**
  - Exhaustive device physical constraints: Spartan-7 resource limits (32,600 LUTs, 65,200 Flip-Flops, 120 DSP48E1 slices, 2,700 Kb Block RAM), FTDI FT2232H USB-UART bridge specifications, power dissipation ceiling ($< 1.5\,$W), and pinout mappings.
- **`MASTER_FPGA_IMPLEMENTATION_AND_FEASIBILITY_REPORT.md` (Authoritative Synthesis Report):**
  - Consolidated hardware synthesis results across extraction candidates: SVD, Wavelet-LMS, Template Subtraction, and PCA Beamforming. Documents DSP slice budget, BRAM consumption, and f_max ($> 100\,$MHz).

### B. Master Algorithmic Architecture & System Decisions
- **`MASTER_ALGORITHM_SELECTION_AND_FPGA_DECISION.md` (Canonical Architectural Decision):**
  - Comprehensive trade-off matrix justifying the selection of **Multi-Channel Causal Spatial PCA Beamforming** over SVD and iterative LMS for Spartan-7 deployment. Demonstrates $93.4\%$ F1-score with $< 22$ DSP48E1 slices and $4.8\%$ total slice LUT utilization.
- **`FECG_MEGA_VALIDATION_FINAL_REPORT.md`:**
  - Executive sign-off report for population-wide validation across all 250 PhysioNet records under adverse $-14\,$dB to $0\,$dB SNR.

### C. Academic Literature & Research Notes
- **`FECG_FPGA_Literature_Notes.md` (55.2 KB):**
  - Deep-dive survey of 20+ years of fetal ECG extraction literature (Sameni, Ungureanu, Pan-Tompkins, CinC 2013).
- **`papers/` (9 PDF References, 14.97 MB):**
  - Landmark peer-reviewed papers:
    1. *Fetal ECG extraction from single-channel maternal ECG using singular value decomposition* (SVD baseline).
    2. *Digital Filters for Real-Time ECG Signal Processing Using Microprocessors*.
    3. *A Review of Signal Processing Techniques for Non-Invasive Fetal Electrocardiography*.
    4. S12575-009-9006-z & Wiley chapters on biopotential amplification.
- **`page/` (2 PDF files):**
  - Extracted figures and pages from conference review templates.
- **`refs_audit.md` & `papers.txt`:**
  - Literature cross-reference verification and citation audits.

### D. Team Management & Tracking
- **`README.md` (Root):**
  - Master entry point outlining executive summary, team roles (Naman, Vivek, Anshu Ram, Astitva), signal processing cascade, and IEEE CVF review guidelines.
- **`TEAM_TASKS_AND_WORK_TRACKER.md`:**
  - Active sprint tracker covering Tasks 1 through 10, deliverables, and numerical audit sign-offs.
- **`UNRESOLVED.md`:**
  - Log of open architectural questions, fixed-point SQNR margins, and hardware synthesis targets.
- **`fecg_team_work_plan.md` & `Fetal_ECG_Project_Context_and_Plan.md`:**
  - Original roadmap and phase milestones.
- **`docs/archive/team_trackers/`:**
  - Archived individual member trackers (`PROJECT_CONTEXT_AND_NAMAN_TRACKER.md`, `ANSHU`, `ASTITVA`, `VIVEK`).

### E. Submission & Milestone Changelogs
- **`CHANGELOG_MTR8.md`:**
  - Formal 18-page IEEE CVF Mid-Term Report revision audit log.

---

## 3. Authoritative vs Superseded Documentation Mapping

| Topic | Canonical Authoritative Document | Superseded / Archived Documents |
| :--- | :--- | :--- |
| **FPGA Architecture & RTL Spec** | `FPGA_SPEC.md` + `DATASHEETS_AND_HARDWARE_SPECS.md` | `docs/archive/fpga_reports/*` (Naman, Vivek, Anshu, Astitva individual reports) |
| **Algorithmic Selection Decision** | `MASTER_ALGORITHM_SELECTION_AND_FPGA_DECISION.md` | `Fetal_ECG_Preliminary_Report_Missing_Sections.md` |
| **Active Team Tracker** | `TEAM_TASKS_AND_WORK_TRACKER.md` | `docs/archive/team_trackers/*`, `fecg_team_work_plan.md` |
| **Mid-Term Submission Changelog** | `CHANGELOG_MTR8.md` | Package-internal changelogs |
| **UART Telemetry Spec** | `FETAL_ECG_FINAL_PRE_RTL_VERIFICATION_PACKAGE/07_uart/UART_PROTOCOL_SPEC_FINAL.md` | Earlier protocol specs in package v1/v2 |

---

## 4. Critical Configuration Files to Preserve

1. **`.gitignore` (Root):**
   - Configured to ignore `data/`, `.venv/`, `venv/`, `__pycache__/`, `*.pyc`, `.DS_Store`. Must remain intact at root.
2. **`CLAUDE.md` (Root):**
   - Core behavioral rules and surgical engineering guidelines for LLM code modification. Must remain intact at root.
3. **`code/requirements.txt`:**
   - Defines runtime environment: `numpy`, `scipy`, `wfdb`, `torch`, `pyyaml`, `pytest`, `pandas`.
   - *Recommendation:* Promote to root `requirements.txt` while maintaining backwards-compatible symlink or reference.
4. **`.agents/`:**
   - Contains graphify rules (`.agents/rules/graphify.md`) and workflows (`.agents/workflows/graphify.md`). Must remain intact.

---

## 5. Proposed Documentation & Hardware Directory Structure

```text
docs/
├── architecture/                     # System design & algorithmic decisions
│   ├── MASTER_ALGORITHM_SELECTION.md
│   ├── MEGA_VALIDATION_FINAL_REPORT.md
│   └── PROJECT_CONTEXT_AND_PLAN.md
├── literature/                       # Academic literature & survey notes
│   ├── LITERATURE_SURVEY_NOTES.md   # (from FECG_FPGA_Literature_Notes.md)
│   ├── REFERENCES_AUDIT.md          # (from refs_audit.md)
│   └── papers/                      # (relocated from papers/)
├── trackers/                         # Team management & task tracking
│   ├── TEAM_TASKS_AND_WORK_TRACKER.md
│   └── UNRESOLVED.md
└── archive/                          # Historical reports and milestone snapshots
    ├── changelogs/                  # CHANGELOG_MTR8.md, etc.
    ├── fpga_reports/                # Individual member feasibility reports
    ├── team_trackers/               # Individual member trackers
    └── preliminary/                 # Fetal_ECG_Preliminary_Report_*.md

hardware/
├── spec/                             # Authoritative FPGA specifications
│   ├── FPGA_SPEC.md                 # Frozen Spartan-7 spec v0.2
│   ├── DATASHEETS_AND_HARDWARE_SPECS.md
│   └── MASTER_FPGA_FEASIBILITY_REPORT.md
├── telemetry/                        # UART communication & telemetry
│   ├── UART_PROTOCOL_SPEC.md        # Canonical UART protocol spec
│   └── PACKET_FRAMING_SPEC.md
└── rtl_prep/                         # Pre-RTL parameters, LUTs, and hex dumps
    └── FINAL_HARDWARE_PARAMETERS.json
```

---
*Report compiled autonomously by Teamwork Documentation & FPGA Auditor.*
