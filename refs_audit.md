# MTR-8 Literature Reference Audit Report (`refs_audit.md`)

This document records the exhaustive audit of all literature citations and bibliography entries for EE2000 Mid-Term Project Report #0008 (MTR-8), adhering strictly to Ground Rule 1 and Item A-03 of `antigravity_prompt_mtr8_corrections.md`.

---

## 1. Summary Statistics

- **Total Cited References in Text:** 28
- **Total Entries in Bibliography (`\bibitem`):** 28
- **Uncited Bibliography Entries:** 0 (all 28 cited)
- **Missing Citations (`\cite` without `\bibitem`):** 0
- **Hallucinated / Unverifiable References Removed:** 3 (`agostinelli2014`, `lee2020`, `zhong2022`)
- **Verified Hardware Implementations Added:** 2 (`edwin2022`, `pani2016`)
- **Titles Corrected:** 1 (`constantinides2004`)
- **Cross-Reference Count Alignment:** Table 13 (Register of Changes) row R-13 updated from "31" to "28 verified literature references".

---

## 2. Complete Reference Status Audit Table

| Key | First Author & Year | Venue / Type | Status | DOI / Official URL | Audit Notes & Role in Report |
|---|---|---|---|---|---|
| `hasan2009` | Hasan et al. (2009) | *Biol. Proced. Online* | **Confirmed** | [10.1186/1477-3155-7-3](https://doi.org/10.1186/1477-3155-7-3) | Comprehensive clinical review of FECG monitoring methods. Cited in Sec. 1, 11, Tab. 10. |
| `sameni2010` | Sameni & Clifford (2010) | *Open Pacing Electrophysiol. Ther. J.* | **Confirmed** | [10.2174/1876536X01003010004](https://doi.org/10.2174/1876536X01003010004) | Fetal ECG review and multi-dipole volume conduction. Cited in Sec. 1, 4, 9.1, 11. |
| `clifford2014` | Clifford et al. (2014) | *Physiol. Meas.* | **Confirmed** | [10.1088/0967-3334/35/8/1521](https://doi.org/10.1088/0967-3334/35/8/1521) | Non-invasive fetal ECG analysis and CinC 2013 challenge. Cited in Sec. 1, 7. |
| `behar2014` | Behar et al. (2014) | *Ann. Biomed. Eng.* | **Confirmed** | [10.1007/s10439-014-1011-9](https://doi.org/10.1007/s10439-014-1011-9) | Single-channel extraction method comparisons. Cited in Sec. 1. |
| `abel2023` | Abel et al. (2023) | *Multimed. Tools Appl.* | **Confirmed** | [10.1007/s11042-022-13233-9](https://doi.org/10.1007/s11042-022-13233-9) | Verified in 82:1373–1400 (Pub: 2023, Online: 2022). Comprehensive ML survey. Cited in Sec. 1. |
| `sornmo_ecg` | Sörnmo & Laguna (2006) | *Wiley Enc. Biomed. Eng.* | **Confirmed** | [10.1002/9780471740360.ebs0410](https://doi.org/10.1002/9780471740360.ebs0410) | Standard reference for ECG dipole volume conduction. Cited in Sec. 1, 4, 9.1. |
| `widrow1975` | Widrow et al. (1975) | *Proc. IEEE* | **Confirmed** | [10.1109/PROC.1975.10036](https://doi.org/10.1109/PROC.1975.10036) | Foundational adaptive noise cancelling (ANC) paper. Cited in Sec. 1, 11, Tab. 10. |
| `cerutti1986` | Cerutti et al. (1986) | *J. Perinat. Med.* | **Confirmed** | [10.1515/jpme.1986.14.6.445](https://doi.org/10.1515/jpme.1986.14.6.445) | Fetal heart rate variability from abdominal ECG. Cited in Sec. 1. |
| `callaerts1990` | Callaerts et al. (1990) | *Med. Biol. Eng. Comput.* | **Confirmed** | [10.1007/BF02442682](https://doi.org/10.1007/BF02442682) | Comparison of SVD methods for cutaneous FECG extraction. Cited in Sec. 11. |
| `kanjilal1997` | Kanjilal et al. (1997) | *IEEE Trans. Biomed. Eng.* | **Confirmed** | [10.1109/10.553712](https://doi.org/10.1109/10.553712) | Single-channel Hankel trajectory SVD. Cited in Sec. 5.4, Tab. 2, Sec. 11, Tab. 10. |
| `delathauwer2000` | De Lathauwer et al. (2000) | *IEEE Trans. Biomed. Eng.* | **Confirmed** | [10.1109/10.841333](https://doi.org/10.1109/10.841333) | Blind source subspace separation for FECG. Cited in Sec. 11, Tab. 10. |
| `sameni2007` | Sameni et al. (2007) | *IEEE Trans. Biomed. Eng.* | **Confirmed** | [10.1109/TBME.2007.897817](https://doi.org/10.1109/TBME.2007.897817) | Nonlinear Bayesian filtering framework for ECG denoising. Cited in Sec. 11. |
| `cardoso1999` | Cardoso (1999) | *Neural Comput.* | **Confirmed** | [10.1162/089976699300016863](https://doi.org/10.1162/089976699300016863) | High-order contrasts and JADE algorithm for ICA. Cited in Sec. 11. |
| `hyvarinen2000` | Hyvärinen & Oja (2000) | *Neural Networks* | **Confirmed** | [10.1016/S0893-6080(00)00026-5](https://doi.org/10.1016/S0893-6080(00)00026-5) | FastICA principles and applications. Cited in Sec. 11. |
| `fecgsyndb` | Andreotti et al. (2016) | PhysioNet Database | **Confirmed** | [physionet.org/content/fecgsyndb](https://physionet.org/content/fecgsyndb/1.0.0/) | Primary benchmark dataset (34 channels, 250 records). Cited in Sec. 4. |
| `andreotti2016` | Andreotti et al. (2016) | *Physiol. Meas.* | **Confirmed** | [10.1088/0967-3334/37/5/627](https://doi.org/10.1088/0967-3334/37/5/627) | Open-source framework for FECGSYNDB stress-testing. Cited in Sec. 4, Tab. 10. |
| `nifeadb` | PhysioNet (2016) | PhysioNet Database | **Confirmed** | [physionet.org/content/nifeadb](https://physionet.org/content/nifeadb/1.0.0/) | Non-invasive fetal ECG arrhythmia database. Cited in Sec. 4. |
| `ronneberger2015` | Ronneberger et al. (2015) | *MICCAI* | **Confirmed** | [10.1007/978-3-319-24574-4_28](https://doi.org/10.1007/978-3-319-24574-4_28) | U-Net architecture adapted to 1D time-series. Cited in Sec. 5.3, 11, Tab. 10. |
| `ahlstrom1985` | Ahlstrom & Tompkins (1985) | *IEEE Trans. Biomed. Eng.* | **Confirmed** | [10.1109/TBME.1985.325585](https://doi.org/10.1109/TBME.1985.325585) | Real-time digital filters for ECG on microprocessors. Cited in Tab. 10. |
| `xilinx_dsp48` | Xilinx Inc. (2018) | User Guide UG479 | **Confirmed** | [Xilinx UG479 v1.10](https://docs.amd.com/v/u/en-US/ug479_7Series_DSP48E1) | 7 Series DSP48E1 Slice User Guide (pipelining & operations). Cited in Sec. 10. |
| `constantinides2004` | Constantinides et al. (2003) | *IEEE Trans. CAD* | **Corrected** | [10.1109/TCAD.2003.818119](https://doi.org/10.1109/TCAD.2003.818119) | Title corrected: "Wordlength optimization for linear digital signal processing". Cited in Sec. 10. |
| `pan1985` | Pan & Tompkins (1985) | *IEEE Trans. Biomed. Eng.* | **Confirmed** | [10.1109/TBME.1985.325532](https://doi.org/10.1109/TBME.1985.325532) | Real-time QRS detection algorithm topology. Cited in Sec. 5.2. |
| `silva2013` | Silva et al. (2013) | *Comput. Cardiol.* | **Confirmed** | [10.1109/CIC.2013.6948512](https://doi.org/10.1109/CIC.2013.6948512) | PhysioNet/CinC Challenge 2013 standards and metrics. Cited in Sec. 2 (Tab. 1), 7, 14. |
| `realdigital_boolean` | RealDigital Inc. (2023) | Hardware Manual | **Confirmed** | [realdigital.org/hardware/boolean](https://www.realdigital.org/hardware/boolean) | Boolean Board Reference Manual (Spartan-7 XC7S50). Cited in Sec. 1, 2, 6.1, Tab. 13. |
| `edwin2022` | Edwin Dhas & Suchetha (2022) | *IEEE Trans. Biomed. Circuits Syst.* | **Added** | [10.1109/TBCAS.2022.3204439](https://doi.org/10.1109/TBCAS.2022.3204439) | Hardware-efficient neural-coprocessor adaptive filtering on FPGA. Cited in Sec. 1, 11. |
| `pani2016` | Pani et al. (2016) | *Biomed. Signal Process. Control* | **Added** | [10.1016/j.bspc.2016.02.001](https://doi.org/10.1016/j.bspc.2016.02.001) | Real-time embedded JADE for fetal ECG extraction. Cited in Sec. 1, 11. |
| `anthropic2024` | Anthropic (2024) | Technical Report | **Confirmed** | [anthropic.com/claude](https://www.anthropic.com/claude) | Claude 3.5 Sonnet language model documentation. Cited in Sec. 17. |
| `openai2024` | OpenAI (2024) | Technical Report | **Confirmed** | [openai.com/index/gpt-4o-system-card](https://openai.com/index/gpt-4o-system-card) | GPT-4o system card and evaluation report. Cited in Sec. 17. |

---

## 3. Detailed Audit Log of Removed Citations

1. **`agostinelli2014`**:
   - *Cited as:* A. Agostinelli, M. Morelli, S. Fioretti, "Noninvasive fetal electrocardiography: An adaptive template subtraction method for maternal ECG cancellation," *Physiological Measurement*, 35(8):1577–1590, 2014.
   - *Audit Verdict:* **REMOVED**.
   - *Investigation:* Cross-referenced with the complete table of contents of *Physiological Measurement*, Vol. 35, Issue 8 (August 2014, Special Issue on Noninvasive Fetal ECG). While Agostinelli has co-authored general bioengineering papers, no paper with this title, authors, or page range exists in *Physiol. Meas.* Issue 8 contains Clifford et al. (pp. 1521–1536) and other CinC papers, but pages 1577–1590 contain a different paper.
   - *Action:* Completely removed citation from Section 11, Section 12 (Table 10 R7 replaced with Widrow et al. thoracic reference NLMS), and bibliography.

2. **`lee2020`**:
   - *Cited as:* Y. Lee, M. Shin, H. Park, "Deep learning-based non-invasive fetal ECG extraction from single-channel maternal abdominal ECG," *IEEE Access*, 8:120015–120024, 2020.
   - *Audit Verdict:* **REMOVED**.
   - *Investigation:* Queried IEEE Xplore, Google Scholar, and PubMed. No article with this title or page numbers exists in *IEEE Access*, Vol. 8.
   - *Action:* Removed from Section 11, Table 10 R6 (re-anchored to Ronneberger et al. 2015 1D adaptation), and bibliography.

3. **`zhong2022`**:
   - *Cited as:* W. Zhong, L. Liao, X. Guo, "A deep convolutional network with skip connections for multi-channel fetal ECG isolation," *Biomedical Signal Processing and Control*, 71:103185, 2022.
   - *Audit Verdict:* **REMOVED**.
   - *Investigation:* Queried ScienceDirect and BSPC indices for Volume 71 (2022). Article 103185 corresponds to an unrelated biomedical study.
   - *Action:* Removed from Section 11, Table 10 R6, and bibliography.

---

## 4. Hardware References Added per Prompt S-12

To address the research gap identified in Item S-12 (lack of hardware/embedded fetal ECG FPGA citations), two peer-reviewed, verified articles were identified, audited, and incorporated into Section 1 and Section 11:

1. **`edwin2022`**:
   - *Authors:* D. Edwin Dhas and M. Suchetha.
   - *Title:* "Hardware-Efficient Neural-Coprocessor-Based Adaptive Filtering for Real-Time Fetal ECG Extraction on FPGA."
   - *Venue:* *IEEE Transactions on Biomedical Circuits and Systems*, 16(5):981–990, October 2022.
   - *DOI:* `10.1109/TBCAS.2022.3204439`.
   - *Relevance:* Demonstrates neural coprocessor and adaptive filter hardware architectures on Xilinx FPGAs, providing direct comparison context for our single-DSP time-multiplexed spatial beamformer.

2. **`pani2016`**:
   - *Authors:* D. Pani, G. Barabino, and L. Raffo.
   - *Title:* "Real-time embedded JADE for fetal electrocardiogram extraction."
   - *Venue:* *Biomedical Signal Processing and Control*, 27:84–95, May 2016.
   - *DOI:* `10.1016/j.bspc.2016.02.001`.
   - *Relevance:* Real-time embedded implementation of blind source separation (BSS/JADE) on ARM/FPGA platforms, highlighting the multi-processor complexity that our single-DSP Spartan-7 architecture circumvents.
