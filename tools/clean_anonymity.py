"""
tools/clean_anonymity.py
Scans code/src and replaces student names and identifying roles with anonymous roles.
"""
import os
import re

replacements = [
    (r'Owner\s*:\s*Vivek[^\n]*', 'Role     : Data Validation & Evaluation Lead'),
    (r'Owner\s*:\s*Anshu[^\n]*', 'Role     : QRS Detection & Template Subtraction Lead'),
    (r'Owner\s*:\s*Naman[^\n]*', 'Role     : Integration & SVD Extraction Lead'),
    (r'Author\s*:\s*Naman[^\n]*', 'Role   : Integration Lead & SVD Extraction Lead'),
    (r'Author\s*:\s*Vivek[^\n]*', 'Role   : Hardware Evaluation Lead'),
    (r"Vivek's Method", "Wavelet-Threshold Hybrid Method"),
    (r"Vivek's Alternative Extractor", "Wavelet-Threshold Alternative Extractor"),
    (r"\(Vivek's pseudo-ensemble alternative method\)", "(Wavelet-Threshold Subband Hybrid)"),
    (r"Vivek's SVD-Template Subband Hybrid Filter", "Wavelet-Threshold Subband Hybrid Filter"),
    (r'extractor_vivek', 'extractor_wavelet_thr'),
    (r'#.*Vivek Hybrid Alternative.*', '# 5. Single-Channel: Wavelet-Threshold Hybrid'),
    (r'"Vivek_Hybrid_Alt"', '"Wavelet_Threshold_Hybrid"'),
    (r"Anshu's method", "Maternal Template Subtraction method"),
    (r'\(Anshu\)', '(Template Subtraction)'),
    (r'\(Vivek\)', '(Wavelet-Threshold Hybrid)'),
    (r'not Naman\'s responsibility', 'outside primary workstream'),
]

for root, dirs, files in os.walk('code/src'):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8') as fp:
                content = fp.read()
            orig = content
            for pat, rep in replacements:
                content = re.sub(pat, rep, content)
            if content != orig:
                with open(p, 'w', encoding='utf-8') as fp:
                    fp.write(content)
                print(f'Cleaned anonymity tokens in {p}')
