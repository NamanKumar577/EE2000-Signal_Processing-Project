# Remaining Implementation Risks & Mitigation Strategies

Even with the algorithm frozen and mathematically verified, hardware and clinical deployment on the RealDigital Boolean Board (Spartan-7 `XC7S50`) involves specific physical risks:

---

## 1. Physical Front-End & ADC Risks

1. **Electrode Half-Cell Potential DC Drift:**
   - *Risk:* Real clinical Ag/AgCl skin electrodes produce DC offsets up to $\pm 300\text{ mV}$, which can saturate 16-bit ADCs if unmanaged.
   - *Mitigation:* The FPGA recursive HP1 filter accumulator has been expanded to **32 bits** (handling up to 28 bits of persistent DC offset). Analog front-end high-pass coupling on the breakout board is required to prevent input ADC saturation.
2. **$50\text{ Hz} / 60\text{ Hz}$ Mains Powerline Hum:**
   - *Risk:* Clinical evaluation on PhysioNet NIFEA showed that 20/26 recordings suffered severe powerline hum. The Config C filter ($12\text{--}35\text{ Hz}$) provides $-24.8\text{ dB}$ attenuation at $50\text{ Hz}$, which may allow residual hum if cable shielding is compromised.
   - *Mitigation:* Proper differential twisted-pair cabling and patient ground reference (right leg drive / DRL) are mandatory. An optional 2-multiplier notch filter module can be enabled in RTL if analog shielding is insufficient.

---

## 2. Physiological & Clinical Operation Risks

3. **Maternal Muscle (EMG) Labor Contraction Noise:**
   - *Risk:* Severe uterine contractions generate high-energy broadband myoelectric interference ($20\text{--}100\text{ Hz}$) that overlaps with the fetal QRS frequency band.
   - *Mitigation:* The host-side autocorrelation confidence gate detects low signal-to-noise windows and asserts a low-confidence status flag, preventing corrupt weight updates and holding the previous valid spatial filter.
4. **Twin Pregnancies:**
   - *Risk:* Clinicians may attempt to use the monitor on multiple gestations.
   - *Mitigation:* Formally classified as **UNSUPPORTED**. A prominent warning is documented: the single-beamformer architecture extracts only the dominant fetal dipole and cannot safely monitor twin pregnancies.

---

## 3. Communication & Clocking Risks

5. **UART Baud Rate Clock Drift:**
   - *Risk:* At $921,600\text{ baud}$, clock deviation between host USB bridge and FPGA greater than $2.5\%$ causes bit framing errors.
   - *Mitigation:* Spartan-7 uses a $100.0\text{ MHz}$ low-jitter oscillator ($50\text{ ppm}$). A 16x oversampling UART receiver FSM with majority voting handles up to $3.5\%$ clock skew. CRC8-CCITT verification discards any corrupted packets.
