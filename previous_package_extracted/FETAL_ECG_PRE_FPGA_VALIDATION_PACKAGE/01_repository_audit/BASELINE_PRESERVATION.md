# Baseline Preservation Verification
All original baseline files remain 100% untouched:
- `code/src/causal_pipeline.py`: Preserved. All 140 original unit tests continue to pass.
- `code/src/fpga_int_model.py`: Preserved. Golden integer model intact.
All newly introduced improvements are cleanly decoupled in:
- `code/src/bit_accurate_reference_model.py`
- `tools/pre_fpga/`
