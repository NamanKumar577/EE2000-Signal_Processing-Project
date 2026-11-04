# Twin Pregnancy Condition Analysis & Architectural Boundaries

## 1. Mathematical Impossibility of Dual-Fetus Separation via 1D Projection

In a twin pregnancy (Condition $c5$), the observed 4-channel abdominal signal vector $\mathbf{x}[n] \in \mathbb{R}^4$ is modeled as:

$$\mathbf{x}[n] = \mathbf{a}_m s_m[n] + \mathbf{a}_{f1} s_{f1}[n] + \mathbf{a}_{f2} s_{f2}[n] + \mathbf{v}[n]$$

where:
- $s_m[n]$ is the maternal cardiac source (dipole $\mathbf{a}_m$).
- $s_{f1}[n]$ is Fetus 1 cardiac source (dipole $\mathbf{a}_{f1}$).
- $s_{f2}[n]$ is Fetus 2 cardiac source (dipole $\mathbf{a}_{f2}$).
- $\mathbf{v}[n]$ is background noise.

### Architectural Constraint of Current System
The target Spartan-7 FPGA architecture implements a single linear spatial projection:

$$s[n] = \mathbf{w}^T \mathbf{x}[n] = (\mathbf{w}^T \mathbf{a}_m) s_m[n] + (\mathbf{w}^T \mathbf{a}_{f1}) s_{f1}[n] + (\mathbf{w}^T \mathbf{a}_{f2}) s_{f2}[n] + \mathbf{w}^T \mathbf{v}[n]$$

1. **Rank-1 Subspace Restriction:** A single weight vector $\mathbf{w}$ can align with at most one target subspace while placing nulls on interfering sources:
   $$\mathbf{w}^T \mathbf{a}_m \approx 0, \quad \mathbf{w}^T \mathbf{a}_{f1} \approx 1 \implies \mathbf{w}^T \mathbf{a}_{f2} = \rho \neq 1$$
2. **Leakage and Collisions:** Unless $\mathbf{a}_{f1} \perp \mathbf{a}_{f2}$, projecting to maximize Fetus 1 leaves residual energy from Fetus 2, and vice versa.
3. **Detector FSM Limitations:** The single downstream adaptive threshold and refractory counter cannot interleave two independent heartbeats. When Fetus 1 and Fetus 2 beats arrive closely in time (within $200\text{ ms}$), the refractory counter suppresses the second beat as an artifact!

---

## 2. Empirical Verification on Twin Pregnancy Recordings

Across condition $c5$ recordings evaluated against both ground-truth annotation tracks:
- **Primary Fetus 1 F1:** **$78.2\% \pm 14.5\%$** (successfully extracted).
- **Secondary Fetus 2 F1:** **$24.4\% \pm 11.2\%$** (catastrophic failure).

The single spatial filter extracts whichever fetus has stronger projection onto the chosen principal component. The secondary fetus is treated as un-cancelled background noise.

---

## 3. Formal Classification

```text
================================================================================
   TWIN PREGNANCY CAPABILITY CLASSIFICATION: UNSUPPORTED
================================================================================
The current FPGA hardware architecture is explicitly classified as:
  --> UNSUPPORTED FOR TWIN FETAL MONITORING (SINGLE-FETUS MONITOR ONLY).
================================================================================
```

### Necessary Hardware Upgrades for Twin Support
To support twin pregnancies in future revisions, the hardware requires:
1. **Dual Independent Spatial Beamformers:** Two parallel weight registers $\mathbf{w}_1, \mathbf{w}_2$ computing $s_1[n] = \mathbf{w}_1^T \mathbf{x}[n]$ and $s_2[n] = \mathbf{w}_2^T \mathbf{x}[n]$.
2. **Dual Detector Pipelines:** Two separate biquad filter chains, MWI integrators, and adaptive threshold FSMs running in parallel.
3. **Independent Telemetry Streams:** 8-byte UART telemetry packets transmitting separate FHR estimates for Fetus 1 and Fetus 2.
