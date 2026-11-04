import re

path = r'c:\Users\ASTITVA\OneDrive\Desktop\EE2000-Signal_Processing-Project\code\tests\test_method_interface.py'

with open(path, 'r') as f:
    content = f.read()

# Remove SWTLMSSNFExtractor from the unimplemented parametrize list
content = content.replace(
    '        TemplatSubtractionExtractor, SWTLMSSNFExtractor, AlternativeExtractor,',
    '        TemplatSubtractionExtractor, AlternativeExtractor,'
)

# Append new SWT smoke tests right before "class TestSVDInterface"
new_tests = """
    def test_swt_lms_ssnf_runs_and_returns_correct_shape(self):
        from src.methods.base import OUTPUT_KEYS
        extractor = SWTLMSSNFExtractor(fs=FS)
        mixture = _make_synthetic_mixture()
        fecg_est, metadata = extractor.run(mixture)
        assert fecg_est.shape == (N,)
        assert np.all(np.isfinite(fecg_est))
        for key in OUTPUT_KEYS:
            assert key in metadata
        assert metadata["input_condition"] == "single_channel"
        assert metadata["runtime_s"] > 0

    def test_swt_lms_ssnf_lms_only_variant(self):
        extractor = SWTLMSSNFExtractor(fs=FS, config={"variant": "lms_only"})
        mixture = _make_synthetic_mixture()
        fecg_est, metadata = extractor.run(mixture)
        assert fecg_est.shape == (N,)
        assert np.all(np.isfinite(fecg_est))
        assert metadata["variant"] == "lms_only"

    def test_swt_lms_ssnf_oracle_mode_labelled_correctly(self):
        extractor = SWTLMSSNFExtractor(fs=FS)
        mixture = _make_synthetic_mixture()
        oracle_ref = np.random.randn(N) * 0.5
        fecg_est, metadata = extractor.run(mixture, reference_channel=oracle_ref)
        assert fecg_est.shape == (N,)
        assert np.all(np.isfinite(fecg_est))
        assert metadata["input_condition"] == "oracle_assisted"

"""

content = content.replace('\n\nclass TestSVDInterface:', new_tests + '\nclass TestSVDInterface:')

with open(path, 'w') as f:
    f.write(content)

print("Done")
