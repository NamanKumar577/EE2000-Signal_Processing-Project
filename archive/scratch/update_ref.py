with open('src/fecg/hardware/bit_accurate_reference.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('\r\n', '\n')
lines = text.split('\n')

cutoff = -1
for idx, l in enumerate(lines):
    if l.startswith('def run_bit_accurate_pipeline_final'):
        cutoff = idx
        break

new_fn = '''def run_bit_accurate_pipeline_final(
    x_q: np.ndarray,                 # (N, 4) Signed 16-bit samples (Q12)
    w_q: np.ndarray,                 # (4,) Signed 16-bit weights (Q1.15)
    mwi_len: int = MWI_WINDOW_LEN,   # 30 samples (120 ms)
    refractory: int = REFRACTORY_SAMPLES, # 50 samples (200 ms)
    warmup: int = 512,               # 512 samples (~2.05 s)
    loc_window: int = 26,            # 26 samples (104 ms)
    latency: int = LATENCY_COMPENSATION_SAMPLES, # 18 samples
    target_weights: Optional[Sequence[Tuple[int, Sequence[int]]]] = None # List of (sample_idx, new_weights)
) -> BitAccurateFinalResult:
    """
    Final Pre-RTL Bit-Accurate Execution Reference Model.
    Strictly adheres to hardware arithmetic wordlengths:
      - 32-bit projection accumulation
      - 48-bit biquad state clamping
      - 36-bit MWI accumulation
      - Pure integer median-5
      - 64-sample linear weight crossfade
      - Per-stage saturation and overflow instrumentation
    """
    runner = BitAccuratePipelineRunner(
        w_initial=w_q,
        mwi_len=mwi_len,
        refractory=refractory,
        warmup=warmup,
        loc_window=loc_window,
        latency=latency
    )
    return runner.process_block(x_q, target_weights=target_weights)
'''

result = '\n'.join(lines[:cutoff]) + '\n\n' + new_fn
with open('src/fecg/hardware/bit_accurate_reference.py', 'w', encoding='utf-8', newline='\n') as f:
    f.write(result)
print('Updated bit_accurate_reference.py successfully.')
