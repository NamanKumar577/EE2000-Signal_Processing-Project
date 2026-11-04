"""
fecg - Multichannel Fetal ECG Extraction & Spartan-7 FPGA Implementation
EE2000 Signal Processing Project (Paper ID: 0008)
"""

__version__ = "1.0.0"

# Core exports
from fecg.core.preprocessing import preprocess
from fecg.core.data_loader import load_record, load_annotations
from fecg.core.evaluation import match_beats, compute_beat_metrics, compute_waveform_metrics
from fecg.detection.qrs_detector import detect_fetal_qrs, QRSDetectorConfig
from fecg.detection.fhr import compute_fhr_series, compute_fhr, compare_fhr, apply_interval_fusion, causal_median5_rr
from fecg.pipelines.causal_pipeline import CausalConfig, CalibrationBank, run_causal
from fecg.hardware.fpga_int_model import run_int_pipeline, compare_with_float, IntResult, BiquadInt

__all__ = [
    "preprocess",
    "load_record",
    "load_annotations",
    "match_beats",
    "compute_beat_metrics",
    "compute_waveform_metrics",
    "detect_fetal_qrs",
    "QRSDetectorConfig",
    "compute_fhr_series",
    "compute_fhr",
    "compare_fhr",
    "apply_interval_fusion",
    "causal_median5_rr",
    "CausalConfig",
    "CalibrationBank",
    "run_causal",
    "run_int_pipeline",
    "compare_with_float",
    "IntResult",
    "BiquadInt",
]
