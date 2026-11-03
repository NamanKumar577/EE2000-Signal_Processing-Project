# Audit of Previous Failures and Retries

1. QRS Raw Metric Table Inversion:
   - Root Cause: Total detections (109,923) was confused with total reference beats (94,162).
   - Fix: Reconciled directly from CSV sums; micro and macro averages explicitly reported.
2. PC3 Calibration Fallback Failure:
   - Root Cause: Forcing PC3 fallback degraded F1 by 12.05 pp on triggered cases.
   - Fix: PC3 fallback permanently eliminated.
3. Group Delay Compensation Latency Mismatch:
   - Root Cause: Hardcoded latency was 12 samples instead of 18 samples for Config C.
   - Fix: Updated latency to 18 samples, restoring 91.17% exact 0-sample match.
4. Telemetry Bit-Packing Overflow:
   - Root Cause: Claimed RR in [60, 300] was packed into 6 bits.
   - Fix: Re-architected Byte 6 status field; FHR transmitted in 0.1 bpm units.
