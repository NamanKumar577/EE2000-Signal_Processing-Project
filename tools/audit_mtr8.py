"""
tools/audit_mtr8.py
Root entrypoint delegating to report/mid_term/tools/audit_mtr8.py.
"""
import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
report_tools = os.path.abspath(os.path.join(base_dir, '..', 'report', 'mid_term', 'tools'))
if report_tools not in sys.path:
    sys.path.insert(0, report_tools)

from audit_mtr8 import run_audit

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="MTR-8 Verification Audit")
    parser.add_argument('--out', type=str, default=None, help="Output file path (saved in UTF-8)")
    args = parser.parse_args()
    
    if args.out:
        import io
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            success = run_audit()
        finally:
            sys.stdout = old_stdout
        output_str = buf.getvalue()
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(output_str)
        sys.exit(0 if success else 1)
    else:
        success = run_audit()
        sys.exit(0 if success else 1)
