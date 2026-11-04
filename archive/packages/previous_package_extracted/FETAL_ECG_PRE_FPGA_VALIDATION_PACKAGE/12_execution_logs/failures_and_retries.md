# Failures and Retries Log
1. Task A LinAlgError in Condition c3:
   - Root Cause: FECGSYNDB simulation bug injected IEEE NaNs into uterine contraction EHG noise (noise1.dat).
   - Resolution: Identified and audited in MISSING_RECORDS.csv; correctly excluded from benchmark.
2. Task C 1.7-2.3 RR Midpoint Split Failure:
   - Root Cause: Midpoint split fabricated fake beats during genuine decelerations (99.4% false insertions in c2).
   - Resolution: Midpoint split permanently rejected in hardware; M4-Modified retains interval fusion + Median5.
3. Task E HP1 Accumulator Headroom:
   - Root Cause: Steady state DC wander pushed accumulator to 28 bits (exceeding initial 24-bit sizing).
   - Resolution: Sized HP1 accumulator to 32 bits in FIXED_POINT_SPECIFICATION.md.
