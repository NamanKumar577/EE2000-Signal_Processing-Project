# Master Hardware Data Sheets, Component Specifications & Dataset Reference Manual

**Course / Context:** EE2000 Signal Processing Project (Team 8 / PPR-8 / MTR-8)  
**System Title:** Real-Time Multi-Channel Fetal ECG Extraction & QRS/FHR Processor on Spartan-7 FPGA  
**Target Hardware Platform:** RealDigital Boolean Board (AMD / Xilinx Spartan-7 `XC7S50-CSGA324`)  
**Data Repository Locations:** `data/FECGSD/` and `data/Non-Invasive_Fetal_ECG_Arrhythmia_Database/`  
**Document Purpose:** Unified reference manual compiling all manufacturer hardware data sheets, silicon specifications, board pinouts, register limits, and complete technical specifications for all datasets in the project `data/` folder.

---

## 1. Document Index & Specification Hierarchy

```
                            MASTER SPECIFICATION ARCHITECTURE
  ┌──────────────────────────────────────────────┐  ┌──────────────────────────────────────────────┐
  │         PART A: HARDWARE DATA SHEETS         │  │         PART B: DATASET SPECIFICATIONS       │
  ├──────────────────────────────────────────────┤  ├──────────────────────────────────────────────┤
  │ 1. AMD / Xilinx Spartan-7 XC7S50 (DS180/189) │  │ 6. PhysioNet FECGSYNDB (Synthetic Database)  │
  │ 2. RealDigital Boolean Board Reference Manual│  │    • 10 Subjects, 5 SNRs, 5 Conditions       │
  │ 3. 7-Series DSP48E1 Slice User Guide (UG479) │  │    • 34 Channels, 250 Hz, WFDB Format 16     │
  │ 4. 7-Series XADC Dual 12-Bit ADC (UG480)     │  │ 7. PhysioNet NIFEA DB (Real Clinical DB)     │
  │ 5. External Clinical AFE (TI ADS1298)        │  │    • 12 Arrhythmia (ARR) + 14 Normal (NR)    │
  │                                              │  │    • 6 Channels (1 Chest + 5 Abdominal)      │
  └──────────────────────────────────────────────┘  └──────────────────────────────────────────────┘
                                                 │
                                                 ▼
  ┌────────────────────────────────────────────────────────────────────────────────────────────────┐
  │                 PART C: PROJECT HARDWARE SPECIFICATION (FPGA_SPEC.md v0.2)                     │
  │ • Integer Wordlengths: s16 Q1.15 input, s24 Q1.23 datapath, s18 Q3.15 coefficients             │
  │ • Latency Budget: 95 cycles @ 100 MHz (0.95 us / 4,000 us sample period = 99.976% idle)       │
  │ • UART Protocol: 921,600 baud 8N1 (10-byte RX frame @ 250 Hz, 7-byte TX telemetry reply)       │
  └────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

# PART A: HARDWARE DATA SHEETS & SILICON SPECIFICATIONS

---

## 2. AMD / Xilinx Spartan-7 FPGA Datasheet (`XC7S50-CSGA324`)

The Spartan-7 family is AMD / Xilinx's cost-optimized, low-power $28\,\text{nm}$ High-Performance Low-Power (HPL) FPGA series. The target device is the **`XC7S50-1CSGA324C`** (Speed Grade -1, Commercial temperature $0^\circ\text{C}$ to $85^\circ\text{C}$).

```
                             XC7S50-CSGA324 ARCHITECTURE
      ┌────────────────────────────────────────────────────────────────────────┐
      │  32,600 6-Input LUTs (8,150 Slices)   │   65,200 Storage Elements (FF) │
      ├───────────────────────────────────────┼────────────────────────────────┤
      │  120 DSP48E1 Slices (25x18 MACs)      │   75 Block RAMs 36k (2,700 kb) │
      ├───────────────────────────────────────┼────────────────────────────────┤
      │  5 Clock Management Tiles (MMCM+PLL)  │   1 Dual 12-Bit 1 MSPS XADC    │
      ├───────────────────────────────────────┼────────────────────────────────┤
      │  210 User I/O Pins (CSGA324 Package)  │   Core Logic VCCINT = 1.0 V    │
      └────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Silicon Capacity & Hardware Budget Comparison

| Hardware Resource | Spartan-7 `XC7S50` (Target) | Spartan-7 `XC7S25` (Low-Cost) | Artix-7 `XC7A35T` (Alt.) | Team 8 Causal Pipeline Need | Spartan-7 Margin |
|---|:---:|:---:|:---:|:---:|:---:|
| **Logic Cells** | 52,160 | 23,360 | 33,280 | ~1,200 | **43.4× headroom** |
| **Configurable LUTs** | 32,600 | 14,600 | 20,800 | 990 (3.04%) | **32.9× headroom** |
| **Flip-Flops (FF)** | 65,200 | 29,200 | 41,600 | 720 (1.10%) | **90.5× headroom** |
| **DSP48E1 Slices** | **120** | **80** | **90** | **1 (0.83%)** | **120× headroom** |
| **Block RAM (BRAM36k)**| **75 (2,700 kb)**| **45 (1,620 kb)**| **50 (1,800 kb)**| **1 (36 kb)** | **75× headroom** |
| **Max Clock (Global)** | 464 MHz | 464 MHz | 464 MHz | 100 MHz | **4.64× headroom** |
| **Core Voltage ($V_{\text{CCINT}}$)**| 1.00 V ± 3% | 1.00 V ± 3% | 1.00 V ± 3% | 1.00 V | — |
| **Estimated Core Power**| 60–120 mW | 45–90 mW | 75–150 mW | **< 30 mW** | **< 0.15 W Board** |

### 2.2 Physical Packaging: CSGA324
- **Package Dimensions:** $15.0\,\text{mm} \times 15.0\,\text{mm}$ footprint.
- **Ball Pitch:** $0.8\,\text{mm}$ fine-pitch ball grid array (324 solder balls arranged as an $18 \times 18$ grid).
- **Thermal Resistance:** $\theta_{JA} = 32.2^\circ\text{C/W}$ (natural convection). At $<0.15\,\text{W}$ dissipation, junction temperature elevation is $<5^\circ\text{C}$ above ambient, requiring no heatsink or cooling fan.

---

## 3. RealDigital Boolean Board Reference Manual

The **RealDigital Boolean Board** is an FPGA development platform engineered around the AMD Spartan-7 `XC7S50-1CSGA324C`.

```
                        BOOLEAN BOARD PERIPHERAL LAYOUT
      ┌────────────────────────────────────────────────────────────────────────┐
      │  [USB Micro-B]  UART (FT2232H) & JTAG Programming Interface           │
      │  [CLK100MHZ]    100.000 MHz Crystal Oscillator                         │
      │  [DISP_AN/CAT]  4-Digit 7-Segment Display (Multiplexed Cathodes)       │
      │  [LED 15..0]    16 Surface-Mount Discrete Green LEDs                   │
      │  [SW 15..0]     16 SPDT Slide Switches                                 │
      │  [BTN 3..0]     4 Pushbuttons (BTN0 = Hardware Reset)                  │
      │  [PMOD A/B/C]   3 Standard 12-pin Digilent Pmod Connectors (3.3V)      │
      │  [XADC Header]  Analog Header (Dedicated Differential + Aux Channels)  │
      └────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Primary Board Peripherals & Master Pin Constraints (`boolean_board.xdc`)

All signals interface via 3.3V LVCMOS (`IOSTANDARD LVCMOS33`):

| Signal Name | FPGA Pin (CSGA324) | Direction | Description & Project Mapping |
|---|:---:|:---:|---|
| `CLK100MHZ` | **`E3`** | Input | 100.0 MHz master crystal oscillator ($T_{\text{period}} = 10.0\,\text{ns}$) |
| `RST_N` | **`J2`** (`BTN[0]`) | Input | Active-Low system master reset (debounced) |
| `UART_RX` | **`V12`** | Input | USB-UART bridge receive line (receives 921,600 baud frames from PC) |
| `UART_TX` | **`U11`** | Output | USB-UART bridge transmit line (telemetry and beat flags to PC) |
| `SW[0]` | **`V2`** | Input | Preset Selection Bit 0 |
| `SW[1]` | **`U2`** | Input | Preset Selection Bit 1 |
| `SW[2]` | **`U1`** | Input | Preset Selection Bit 2 (presets P1..P5 mapped to `SW[2:0]`) |
| `SW[3]` | **`T2`** | Input | Mains Notch Frequency Toggle ($0 = 50\,\text{Hz}, 1 = 60\,\text{Hz}$) |
| `SW[4]` | **`T1`** | Input | Raw Maternal Bypass Toggle ($0 = \text{Clean FECG}, 1 = \text{Raw Lead 27}$) |
| `LED[0]` | **`G1`** | Output | **Fetal Heartbeat Pulse** (stretched to $50\,\text{ms}$ flash on detected beat) |
| `LED[1]` | **`G2`** | Output | Refractory Blanking Active Flag (illuminates during 200 ms lockout) |
| `LED[2]` | **`F1`** | Output | UART Frame Synchronization Lock Indicator |
| `LED[3]` | **`F2`** | Output | FHR Valid Flag ($60 \le RR \le 300\,\text{samples}$) |
| `DISP_AN[0]` | **`H3`** | Output | 7-Segment Digit 0 Anode (Units digit of FHR) |
| `DISP_AN[1]` | **`J4`** | Output | 7-Segment Digit 1 Anode (Tens digit of FHR) |
| `DISP_AN[2]` | **`H4`** | Output | 7-Segment Digit 2 Anode (Hundreds digit of FHR) |
| `DISP_AN[3]` | **`J3`** | Output | 7-Segment Digit 3 Anode (Status indicator: `F` for Fetal) |
| `DISP_CAT[0]`| **`D7`** (A) | Output | 7-Segment Segment A Cathode |
| `DISP_CAT[1]`| **`C7`** (B) | Output | 7-Segment Segment B Cathode |
| `DISP_CAT[2]`| **`D5`** (C) | Output | 7-Segment Segment C Cathode |
| `DISP_CAT[3]`| **`C5`** (D) | Output | 7-Segment Segment D Cathode |
| `DISP_CAT[4]`| **`D6`** (E) | Output | 7-Segment Segment E Cathode |
| `DISP_CAT[5]`| **`C6`** (F) | Output | 7-Segment Segment F Cathode |
| `DISP_CAT[6]`| **`D4`** (G) | Output | 7-Segment Segment G Cathode |

### 3.2 High-Speed USB-UART Bridge Specifications
- **Controller Silicon:** FTDI FT2232H / CP2102N USB-UART bridge.
- **Configured Baud Rate:** **921,600 baud** (8 data bits, no parity, 1 stop bit: `8N1`).
- **Clock Divider Derivation:**
  $$\text{Divider} = \frac{f_{\text{clk}}}{\text{Baud Rate}} = \frac{100{,}000{,}000\,\text{Hz}}{921{,}600\,\text{bps}} \approx 108.507$$
  Accumulated fractional baud rate error using an integer divider of $109$ is $< 0.45\%$, well below the standard $2.5\%$ UART margin.
- **Link Bandwidth Utilization:**
  $$\text{Data Rate} = 10\,\text{bytes/sample} \times 250\,\text{samples/s} = 2{,}500\,\text{bytes/s} = 25{,}000\,\text{baud-bits/s}$$
  $$\eta_{\text{UART}} = \frac{25{,}000}{921{,}600} \approx \mathbf{2.71\%}$$
  Leaves $> 97\%$ of UART capacity idle for bi-directional telemetry and calibration weight loading.

---

## 4. Xilinx 7-Series DSP48E1 Slice Datasheet (UG479)

The DSP48E1 slice is the high-speed arithmetic engine of the Spartan-7 fabric.

```
                           DSP48E1 SLICE DATAPATH (UG479)
               25-Bit Port A                 18-Bit Port B
                    │                              │
                    ▼                              ▼
             [ A1/A2 Regs ]                 [ B1/B2 Regs ]
                    │                              │
                    │        ┌──────────────┐      │
                    │        │ Pre-Adder    │◄─────┘
                    │        │ (D +/- A)    │
                    ▼        └──────┬───────┘
             ┌──────────────────────┴───────────────┐
             │    25 x 18 Two's Complement MAC      │
             └──────────────────────┬───────────────┘
                                    ▼
                              [ MREG Pipeline ]
                                    │
               48-Bit Port C        ▼
                    │        ┌──────────────┐
                    └───────►│ 48-Bit ALU   │◄──── Feedback from P
                             │ (Adder/Logic)│
                             └──────┬───────┘
                                    ▼
                              [ PREG Output ]
                                    │
                                    ▼
                              48-Bit Output P
```

- **Multiplier Geometry:** Two's complement signed $25 \times 18$ bit multiplier.
- **Accumulator Width:** $48\text{-bit}$ internal ALU ($P[47:0]$).
- **Word-Length Mapping in our Pipeline:**
  - **Spatial Projection:** $16\text{-bit } w \times 16\text{-bit } x \rightarrow 32\text{-bit}$ product (fits $25 \times 18$).
  - **Biquad Transposed DF-II:** $18\text{-bit } b \times 24\text{-bit } x \rightarrow 42\text{-bit}$ product (fits $25 \times 18 \rightarrow 48$).
  - **State Updates:** $s_1 = b_1 x - a_1 y + s_2$ and $s_2 = b_2 x - a_2 y$ (accumulated without overflow).
  - **Nonlinear Squaring:** $16\text{-bit } z \times 16\text{-bit } z \rightarrow 32\text{-bit}$ unsigned energy.

---

## 5. Analog Front-End & ADC Data Sheets (UG480 vs TI ADS1298)

| Attribute | Xilinx On-Chip XADC (UG480) | Texas Instruments ADS1298 (SBAS459K) | Our UART Streamed Interface |
|---|:---:|:---:|:---:|
| **ADC Architecture** | Dual 12-Bit SAR | 8-Channel 24-Bit $\Delta\Sigma$ | Digital 16-Bit Stream |
| **Max Sampling Rate** | $1.0\,\text{MSPS}$ | $250\,\text{SPS}$ to $32\,\text{kSPS}$ | Synchronized at $250\,\text{Hz}$ |
| **Dynamic Range** | $66\,\text{dB}$ ($10.7$ ENOB) | **$115\,\text{dB}$** | **$96.3\,\text{dB}$** |
| **Input Referred Noise**| $\approx 100\,\mu\text{V}_{\text{RMS}}$ | **$4.1\,\mu\text{V}_{\text{p-p}}$** | Negligible (Digitized biopotentials) |
| **LSB Resolution** | $244.1\,\mu\text{V/LSB}$ (unbuffered) | $0.024\,\mu\text{V/LSB}$ | **$0.1526\,\mu\text{V/LSB}$** |
| **Fetal Spike Representation**| $< 0.1\,\text{LSB}$ without external preamp | $> 800\,\text{LSBs}$ per fetal spike | **$\approx 131\,\text{LSBs}$ per fetal spike** |
| **Interface to FPGA** | Internal DRP bus / Analog Header | 4-wire SPI (Pmod header) | FTDI USB-UART Bridge (`V12`) |

---

# PART B: DATASET SPECIFICATIONS (`data/` DIRECTORY)

The project workspace maintains two biopotential databases in the `data/` directory:
1. `data/FECGSD/DESTINATION/` (PhysioNet Fetal ECG Synthetic Database)
2. `data/Non-Invasive_Fetal_ECG_Arrhythmia_Database/DESTINATION/` (PhysioNet NIFEA Database)

---

## 6. PhysioNet FECGSYNDB Data Sheet (`data/FECGSD/DESTINATION`)

- **Dataset Identifier:** PhysioNet `fecgsyndb/1.0.0`
- **Citation:** Behar et al., *"A comparison of single-channel fetal ECG extraction methods"*, Annals of Biomedical Engineering, 42(6):1340–1353, 2014.
- **Physical Sampling Frequency ($f_s$):** **$250\,\text{Hz}$** ($T_s = 4.0\,\text{ms}$).
- **Record Duration:** **$300.0\,\text{seconds}$** ($5.0\,\text{minutes}$) = **$75,000\,\text{samples}$ per channel**.
- **Data File Format:** WFDB Format 16 (16-bit signed integer, 2's complement, little-endian, multiplexed by channel).

```
                      FECGSYNDB DIRECTORY HIERARCHY
      data/FECGSD/DESTINATION/
      ├── ANNOTATORS            (Defines "qrs" annotator)
      ├── RECORDS               (Master index listing 7,000 constituent files)
      ├── SHA256SUMS.txt        (Cryptographic integrity hashes)
      ├── images/
      │   ├── fig1.png          (Electrode montage layout map)
      │   └── samplechart.png   (Biopotential signal component chart)
      ├── sub01/ ... sub10/     (10 Simulated Anatomical Subjects)
      │   ├── snr00dB/          (0 dB SNR noise condition)
      │   ├── snr03dB/          (3 dB SNR noise condition)
      │   ├── snr06dB/          (6 dB SNR noise condition)
      │   ├── snr09dB/          (9 dB SNR noise condition)
      │   └── snr12dB/          (12 dB SNR clean baseline condition)
```

### 6.1 Simulation Signal Decomposition & Mixture Equation
In FECGSYNDB, each clinical recording is decomposed into constituent biopotential files. This permits controlled mixing while providing clean reference signals for evaluation:

$$\text{AECG}[n] = \mathbf{x}_{\text{mecg}}[n] + \mathbf{x}_{\text{fecg1}}[n] + \mathbf{x}_{\text{noise1}}[n] + \mathbf{x}_{\text{noise2}}[n]$$

| Component File Suffix | Signal Role | Physical Content & Characteristics | Evaluation Policy |
|---|---|---|---|
| `*_fecg1.dat` / `.hea` | Pure Fetal ECG | Clean fetal cardiac biopotential dipole vector | **Reference Ground Truth ONLY**; NEVER fed to extractor |
| `*_fecg1.qrs` | Fetal Annotations | Exact sample timestamps of every fetal R-peak | Used for sensitivity, PPV, and F1 scoring ($\pm 50\,\text{ms}$) |
| `*_mecg.dat` / `.hea` | Pure Maternal ECG | Clean maternal cardiac dipole vector ($5\times$ to $20\times$ amplitude of fetal) | Combined into abdominal mixture |
| `*_mecg.qrs` | Maternal Annotations| Exact sample timestamps of every maternal R-peak | Used to benchmark maternal R-peak alignment |
| `*_noise1.dat` / `.hea`| Noise Source 1 | Low-frequency baseline wander & maternal respiration | Combined into abdominal mixture |
| `*_noise2.dat` / `.hea`| Noise Source 2 | High-frequency maternal abdominal EMG muscle interference | Combined into abdominal mixture |
| `*_fecg2.dat` / `.hea` | Fetus 2 (Twins) | Secondary fetal cardiac dipole present in condition `c5` | Benchmarks twin pregnancy separation |

### 6.2 Channel Geometry & 34-Lead Topography
Each `.dat` file contains **34 channels** multiplexed sample-by-sample:
- **Channels 0 to 31 (32 Abdominal Leads):** A grid of surface biopotential electrodes placed across the maternal abdomen from epigastric to suprapubic regions.
- **Channels 32 and 33 (2 Thoracic Leads):** Maternal chest reference electrodes capturing the maternal dipole vector with minimal fetal contamination.
- **File Storage Calculation:**
  $$\text{Record Size} = 75{,}000\,\text{samples} \times 34\,\text{channels} \times 2\,\text{bytes/sample} = \mathbf{5{,}100{,}000\,\text{bytes}}\,(5.10\,\text{MB})$$
  The full synthetic dataset contains 7,000 constituent files spanning $33.4\,\text{GB}$.

### 6.3 The Frozen 4-Lead Suprapubic Sub-Array
While single-channel extraction on Lead 0 yields poor performance due to low Fetal-to-Maternal Ratio ($FMR \approx 0.02$), our multi-channel scaling study established an optimal 4-lead sub-array:
$$\mathbf{X}[n] = [x_{27}[n],\, x_{26}[n],\, x_{28}[n],\, x_{25}[n]]^T$$

- **Physical Placement:** Lower abdominal / suprapubic midline directly over the fetal vertex presentation.
- **Dipole Enhancement:** Boosts input FMR to **$0.54$**, allowing 1 DSP48E1 slice to achieve **$93.00\%$ population mean F1** across the entire 250-record database.

### 6.4 Clinical Conditions & Noise Tiers

| Condition Code | Clinical Designation | Physiological Simulation Profile | Primary Signal Processing Challenge |
|:---:|---|---|---|
| **`c0`** | Baseline Normal | Constant fetal HR ($143\,\text{bpm}$), constant maternal HR ($108\,\text{bpm}$) | Additive noise suppression |
| **`c1`** | Movement Artifact | Sudden maternal/fetal postural shifts & breathing swings | Baseline wander + rotating spatial dipole axis |
| **`c2`** | HR Accelerations/Decelerations | Dynamic fetal cardiac decelerations ($90\dots 160\,\text{bpm}$) | Rapidly shifting RR intervals |
| **`c3`** | Uterine Contractions | Periodic high-amplitude abdominal electrohysterogram (EHG) | Dense low-to-mid frequency muscle burst noise |
| **`c4`** | Ectopic Arrhythmia | Premature Ventricular Contractions (PVCs) and extrasystoles | Morphological distortion of cardiac template |
| **`c5`** | Twin Pregnancy | Two independent fetal cardiac sources ($fecg1$ and $fecg2$) | Source separation of overlapping fetal spikes |

### 6.5 WFDB Header Metadata Schema (`.hea`)
Every record contains medical header fields:
```text
sub01_snr12dB_l1_c0_fecg1 34 250 75000
sub01_snr12dB_l1_c0_fecg1.dat 16 3000(0)/nu 0 0 0 11576 0 ECG
... (34 channel lines)
#n:300000             <-- Simulation sample length
#fhr:143.0077         <-- Exact reference fetal heart rate (bpm)
#mhr:107.7705         <-- Exact reference maternal heart rate (bpm)
#mtypeacc:nsr         <-- Maternal cardiac rhythm: Normal Sinus Rhythm
#ftypeacc:nsr         <-- Fetal cardiac rhythm: Normal Sinus Rhythm
#SNRfm:-11.3619       <-- True fetal-to-maternal power ratio (dB)
#mheart:2.0944 0.2 0.4<-- 3D spatial dipole coordinates of maternal heart
#fheart:-0.311 0.334  <-- 3D spatial dipole coordinates of fetal heart
#refpos:3.1416 0.5 -0.3<-- 3D coordinates of reference ground electrode
#ntype:MA MA          <-- Applied noise model: Motion Artifacts
#SNRmn:12             <-- Maternal-to-noise ratio: 12 dB
```

---

## 7. PhysioNet Fetal ECG Arrhythmia Database (`data/Non-Invasive_Fetal_ECG_Arrhythmia_Database/DESTINATION`)

- **Dataset Identifier:** PhysioNet `nifeadb/1.0.0` (Non-Invasive Fetal ECG Arrhythmia Database)
- **Citation:** Behar JA, Bonnemains L, Shulgin V, Oster J, Ostras O, Lakhno I., *"Noninvasive fetal electrocardiography for the detection of fetal arrhythmias"*, Prenatal Diagnosis, 39(8):662–671, 2019.
- **Clinical Nature:** **Real-world in-vivo recordings** from clinical patients at gestational ages between 20 and 40 weeks.
- **Total Records:** **26 clinical recordings**:
  - **12 Arrhythmia recordings (`ARR_01` through `ARR_12`):** Diagnosed fetal arrhythmias including premature atrial contractions (PAC), ventricular extrasystoles (PVC), supraventricular tachycardia (SVT), and atrioventricular heart blocks.
  - **14 Normal Rhythm control recordings (`NR_01` through `NR_14`):** Healthy fetuses in normal sinus rhythm.

```
            NON-INVASIVE FETAL ECG ARRHYTHMIA DATABASE (NIFEA DB)
      data/Non-Invasive_Fetal_ECG_Arrhythmia_Database/DESTINATION/
      ├── HEADER.shtml          (Clinical documentation and diagnosis guide)
      ├── RECORDS               (Index of all 26 records)
      ├── ARR_01.dat / .hea     (Arrhythmia Patient 01: 6 Ch, 1000 Hz, 600,052 samples)
      ├── ...
      ├── ARR_12.dat / .hea     (Arrhythmia Patient 12)
      ├── NR_01.dat / .hea      (Normal Control 01: 6 Ch, 1000 Hz, 600,052 samples)
      ├── ...
      └── NR_14.dat / .hea      (Normal Control 14)
```

### 7.1 Channel Topography & Physical Units
Each patient recording contains **6 channels**:
- **Channel 0 (`ECG`):** Maternal thoracic chest lead (reference for maternal QRS).
- **Channels 1 through 5 (`Abdomen_1` through `Abdomen_5`):** 5 surface electrodes placed over the maternal abdominal wall.
- **Physical Sampling Rate:** **$1{,}000\,\text{Hz}$** (or $500\,\text{Hz}$ on select patient files).
- **Physical Calibration:** Real microvolt calibration with gains recorded per lead (e.g., in `ARR_01.hea`, Lead 1 has gain $61{,}563.18\,\text{counts/mV}$, representing $0.0162\,\mu\text{V/count}$).

### 7.2 Header Inspection: Clinical Record `ARR_01.hea`
```text
ARR_01 6 1000 600052
ARR_01.dat 16 26599.2897(-14247)/mV 16 0 -15331 6038 0 ECG
ARR_01.dat 16 61563.1752(-11451)/mV 16 0 12759 6551 0 Abdomen_1
ARR_01.dat 16 82406.7903(8910)/mV 16 0 -14947 27285 0 Abdomen_2
ARR_01.dat 16 75046.0922(-10478)/mV 16 0 8246 1637 0 Abdomen_3
ARR_01.dat 16 77303.4503(-3624)/mV 16 0 -18466 30364 0 Abdomen_4
ARR_01.dat 16 40590.895(-21371)/mV 16 0 10747 27652 0 Abdomen_5
```
- **Duration:** $600{,}052\,\text{samples} / 1{,}000\,\text{Hz} = 600.05\,\text{seconds} \approx \mathbf{10.0\,\text{minutes}}$.
- **Integration with Spartan-7 Processing Core:** To stream these real-world recordings through our $250\,\text{Hz}$ FPGA core, the Python host streamer (`tools/stream_to_fpga.py`) executes a 4:1 decimation filter ($1000\,\text{Hz} \rightarrow 250\,\text{Hz}$) before packing the 10-byte UART frames.

---

# PART C: PROJECT HARDWARE SPECIFICATION (`FPGA_SPEC.md` v0.2)

---

## 8. Team 8 Frozen RTL Pipeline Specifications

This section summarizes the frozen parameters from [`FPGA_SPEC.md`](file:///d:/signal_project/FPGA_SPEC.md) implemented in [`code/src/fpga_int_model.py`](file:///d:/signal_project/code/src/fpga_int_model.py).

```
                      END-TO-END FPGA CAUSAL DATAPATH
   PC UART Frame [10 Bytes]
         │ (921,600 baud, 250 Hz)
         ▼
   [ UART Receiver & Frame Parser ]
         │
         ▼ 4x s16 (Q1.15) Samples
   [ Spatial PCA Beamformer: w^T x ]  ───► Produces s24 (Q1.23)
         │
         ▼
   [ HP1 Baseline Remover (>> 6) ]     ───► Produces s24 (Q1.23), fc ~ 0.62 Hz
         │
         ▼
   [ LP40 Low-Pass Filter (2 Biquads) ] ───► Produces fecg_out (s24 >> 8 -> s16)
         │
         ▼
   [ BP 8-30Hz Detector (4 Biquads) ] ───► Produces det_bp (s16)
         │
         ▼
   [ Nonlinear Squaring (z^2) ]        ───► Produces u32 energy
         │
         ▼
   [ 20-Sample Trailing MWI Sum ]      ───► Produces u40 integrated energy
         │
         ▼
   [ Adaptive Dual-Threshold Logic ]   ───► Evaluates peak/noise levels & refractory
         │
         ▼
   [ R-Peak Localisation & Argmax ]    ───► 26-sample window, L_comp = 12 samples
         │
         ├───► Beat Flag (1-cycle pulse) ───► LED[0] Heartbeat Stretcher
         │
         ▼
   [ FHR ROM LUT (241x12) ]            ───► 150000 / RR -> FHR (BPM x 10)
         │
         ├───► 7-Segment Display Controller (DISP_AN / DISP_CAT)
         │
         ▼
   [ UART Transmit Packet [7 Bytes] ] ───► Telemetry to Host PC
```

### 8.1 Register Formats and Quantization Allocation

| Register Name | Format | Bit Width | Fractional Bits | Range / Capacity | Physical Logic Mapping |
|---|:---:|:---:|:---:|---|---|
| `x_in[0..3]` | Signed | 16 bits | 15 (Q1.15) | $[-1.0, +0.9999]$ ($\pm 5.0\,\text{mV}$) | Input registers from UART FIFO |
| `w_weights[0..3]` | Signed | 16 bits | 15 (Q1.15) | $[-1.0, +0.9999]$ (Unit vector) | Calibration weight registers |
| `proj_acc` | Signed | 48 bits | 30 (Q2.30) | Measured need: 28 bits | DSP48E1 Accumulator ($P$) |
| `proj_s24` | Signed | 24 bits | 23 (Q1.23) | Rounded `>> 7`, saturated | 24-bit fabric pipeline register |
| `hp_acc` | Signed | 32 bits | 23 (Q1.23) | Measured need: 23 bits | 32-bit fabric adder/subtractor |
| `biquad_coef` | Signed | 18 bits | 15 (**Q3.15**)| Allows numerator coeff = $2.0$ | Distributed LUT ROM or DSP Port B |
| `biquad_state` | Signed | 48 bits | 38 (Q10.38)| Measured need: 36 bits | DSP48E1 $P$-feedback register |
| `fecg_out_s16` | Signed | 16 bits | 15 (Q1.15) | Saturated `>> 8` from s24 | Streaming output to UART TX |
| `det_bp_s16` | Signed | 16 bits | 15 (Q1.15) | Output of 4-biquad bandpass | Squaring multiplier input |
| `sq_energy` | Unsigned| 32 bits | 30 (Q2.30) | Squared biopotential energy | DSP48 multiplier output |
| `mwi_sum` | Unsigned| 40 bits | 30 (Q10.30)| Trailing 20-sample sum | 40-bit accumulator register |
| `spki` (Peak) | Unsigned| 40 bits | 30 (Q10.30)| Signal Peak Level tracking | Updated via `+ (v - spki) >> 3` |
| `npki` (Noise)| Unsigned| 40 bits | 30 (Q10.30)| Noise Peak Level tracking | Updated via `+ (v - npki) >> 3` |
| `rr_samples` | Unsigned| 9 bits | 0 (Integer) | Valid range: $60$ to $300$ samples | Up-counter measuring beat interval|
| `fhr_lut` | Unsigned| 12 bits | 0 (BPM $\times$ 10)| Range: $500$ to $2500$ ($50.0\dots 250.0$ BPM)| $241 \times 12\text{-bit}$ Block RAM or LUT ROM |

### 8.2 UART Protocol Packet Formats

#### 1. PC-to-FPGA Sample Frame (10 Bytes per sample @ 250 Hz)
```
[ Byte 0 ]  0xA5 (Frame Header / Synchronization Byte)
[ Byte 1 ]  Channel 27 Low Byte  (Signed 16-bit Q1.15)
[ Byte 2 ]  Channel 27 High Byte
[ Byte 3 ]  Channel 26 Low Byte  (Signed 16-bit Q1.15)
[ Byte 4 ]  Channel 26 High Byte
[ Byte 5 ]  Channel 28 Low Byte  (Signed 16-bit Q1.15)
[ Byte 6 ]  Channel 28 High Byte
[ Byte 7 ]  Channel 25 Low Byte  (Signed 16-bit Q1.15)
[ Byte 8 ]  Channel 25 High Byte
[ Byte 9 ]  XOR Checksum of Bytes 1 through 8
```

#### 2. FPGA-to-PC Telemetry Frame (7 Bytes reply per sample)
```
[ Byte 0 ]  0x5A (Response Synchronization Byte)
[ Byte 1 ]  Status Flags:
              Bit 0: Fetal QRS Beat Pulse (1 = Beat declared on this sample)
              Bit 1: FHR Valid Flag (1 = Last RR between 60 and 300 samples)
              Bit 2: Warmup Active Flag (1 = Still in initial 512-sample warmup)
              Bits 7..3: Reserved (00000)
[ Byte 2 ]  Filtered FECG Low Byte  (Signed 16-bit Q1.15)
[ Byte 3 ]  Filtered FECG High Byte
[ Byte 4 ]  Instantaneous FHR Low Byte  (Unsigned 16-bit, BPM x 10)
[ Byte 5 ]  Instantaneous FHR High Byte (e.g., 1432 = 143.2 BPM)
[ Byte 6 ]  XOR Checksum of Bytes 1 through 5
```

#### 3. PC-to-FPGA Calibration Weight Frame (9 Bytes, sent once on startup)
```
[ Byte 0 ]  0xC3 (Calibration Weight Header)
[ Byte 1 ]  Weight 0 Low Byte  (Signed 16-bit Q1.15)
[ Byte 2 ]  Weight 0 High Byte
[ Byte 3 ]  Weight 1 Low Byte  (Signed 16-bit Q1.15)
[ Byte 4 ]  Weight 1 High Byte
[ Byte 5 ]  Weight 2 Low Byte  (Signed 16-bit Q1.15)
[ Byte 6 ]  Weight 2 High Byte
[ Byte 7 ]  Weight 3 Low Byte  (Signed 16-bit Q1.15)
[ Byte 8 ]  Weight 3 High Byte
[ Byte 9 ]  XOR Checksum of Bytes 1 through 8
```

---

## 9. Real-Time Hardware Timing Budget

$$\text{Available Clock Budget at 100 MHz} = \frac{100{,}000{,}000\,\text{Hz}}{250\,\text{Hz}} = \mathbf{400{,}000\,\text{clock cycles / sample}}$$

| Execution Stage | Operations | Clock Cycles | Hardware Unit |
|---|---|:---:|---|
| **UART Frame Deserialization** | 10-byte packet decode & parity check | Parallel (Streaming) | Fabric Shift Register |
| **Spatial Beamformer** | 4-point dot product $\mathbf{w}^T \mathbf{x}$ | 4 cycles | DSP48E1 Multiplier |
| **HP1 Baseline Filter** | $y = x - (\text{acc} \gg 6)$ | 1 cycle | Fabric Adder/Shifter |
| **LP40 Low-Pass (Order 4)** | 2 Biquads $\times$ 5 MAC operations | 10 cycles | DSP48E1 Multiplier |
| **BP 8-30 Hz Detector (Order 4)**| 4 Biquads $\times$ 5 MAC operations | 20 cycles | DSP48E1 Multiplier |
| **Energy Squaring** | $z^2[n]$ | 1 cycle | DSP48E1 Multiplier |
| **Trailing MWI Ring Buffer** | Ring FIFO read/sub + newest add | 2 cycles | Fabric Logic |
| **Peak Detection & Thresholding**| Dual SPKI/NPKI update + refractory logic| 4 cycles | Fabric Shifters / Counters|
| **Argmax R-Peak Localisation** | 26-sample circular buffer search | 26 cycles | Dual-port Distributed RAM |
| **FHR ROM Lookup** | Direct address read $RR - 60$ | 1 cycle | Single-port BRAM / ROM |
| **Pipeline Inter-Stage Staging** | Register synchronization delays | 25 cycles | Fabric Flip-Flops |
| **TOTAL DETERMINISTIC LATENCY** | Complete extraction chain | **95 cycles** | **1 DSP48E1 + Fabric** |

### Latency and Compute Margin:
$$\text{Per-Sample Compute Latency} = 95\,\text{cycles} \times 10.0\,\text{ns} = \mathbf{0.95\,\mu\text{s}}$$
$$\text{Real-Time Timing Slack Margin} = \frac{4{,}000\,\mu\text{s} - 0.95\,\mu\text{s}}{4{,}000\,\mu\text{s}} = \mathbf{99.976\%\,\text{idle}}$$

---

## 10. Summary Verification Checklist for FPGA Implementation

- [x] **Pin Constraints Matched:** Clock on `E3`, Reset on `J2`, Heartbeat LED on `G1`, UART RX on `V12`.
- [x] **Word Lengths Aligned:** Inputs and weights are signed Q1.15; coefficients are signed Q3.15; internal states are saturated s24/s48.
- [x] **UART Baud Verified:** $921{,}600\,\text{baud}$ with clock divider of 109 on $100\,\text{MHz}$ clock.
- [x] **Filter Delays Compensated:** Fixed latency compensation $L_{\text{comp}} = 12\,\text{samples}$ implemented in peak declaration.
- [x] **Golden Test Vectors Available:** 5,000 hex-formatted stimulus and reference vectors verified in `code/results/fpga_golden/sub01_snr12_c0/`.
- [x] **Display Ready:** 4-digit multiplexer maps calculated FHR (bpm) to the Boolean Board 7-segment display.
