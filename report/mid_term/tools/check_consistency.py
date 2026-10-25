"""
check_consistency.py
Automated consistency checker matching Section 11 of MTR8_audit_and_fix_plan.md.
"""

import os
import pandas as pd
import numpy as np
from scipy import stats

def check_all():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, '..', '..', '..'))
    
    mega_csv = os.path.join(project_root, 'code', 'results', 'mega_benchmark_results.csv')
    metrics_csv = os.path.join(project_root, 'code', 'results', 'metrics.csv')
    
    print("=" * 60)
    print("MTR-8 CONSISTENCY AUDIT CHECKER")
    print("=" * 60)
    
    # 1. Check Table 3 vs Table 4 on Subject 1
    t3 = pd.read_csv(metrics_csv)
    print(f"\n[E-14 Check] Table 3 row count in metrics.csv: {len(t3)} (Target: 35 runs)")
    assert len(t3) == 35, f"Expected 35 rows in metrics.csv, found {len(t3)}"
    
    # Check TP + FP == Det and TP + FN == Ref
    mismatch_det = (t3['tp'] + t3['fp'] != t3['n_det_beats']).sum()
    mismatch_ref = (t3['tp'] + t3['fn'] != t3['n_ref_beats']).sum()
    print(f"TP+FP == Det mismatches: {mismatch_det}")
    print(f"TP+FN == Ref mismatches: {mismatch_ref}")
    assert mismatch_det == 0 and mismatch_ref == 0
    
    t4 = t3.groupby(['method', 'variant'])[['f1', 'fhr_mae_bpm', 'sensitivity', 'ppv', 'correlation', 'runtime_s']].mean()
    print("\n[E-01 Check] Recomputed Table 4 means for classical methods on sub01:")
    for idx, r in t4.iterrows():
        print(f"  {idx[0]} ({idx[1]}): F1={r['f1']*100:.2f}%, MAE={r['fhr_mae_bpm']:.2f} bpm, Corr={r['correlation']:.3f}")
        
    # 2. Population CI checks
    pop = pd.read_csv(mega_csv)
    print(f"\n[Population Check] Total rows: {len(pop)} (Target: 2250 runs, 250 records x 9 methods)")
    assert len(pop) == 2250
    
    print("\n[Clustered CI Check (df=9, t_crit=2.262)]")
    for meth in pop['method'].unique():
        m_df = pop[pop['method'] == meth]
        sub_means = m_df.groupby('sub_id')['f1'].mean() * 100
        n_subj = len(sub_means)
        hw = stats.t.ppf(0.975, n_subj - 1) * sub_means.std(ddof=1) / np.sqrt(n_subj)
        run_x = m_df['f1'] * 100
        run_se = run_x.std(ddof=1) / np.sqrt(len(run_x))
        run_hw = 1.96 * run_se
        print(f"  {meth:24s}: Pop Mean={sub_means.mean():.2f}% +/- {hw:.2f}% (95% Clustered CI [{sub_means.mean()-hw:.2f}, {sub_means.mean()+hw:.2f}]); Run SE={run_se:.2f}%, 95% Run HW={run_hw:.2f}%")
        
    # 3. Partition specific numbers (E-02, E-03)
    print("\n[E-02, E-03 Partition Breakdown Check]")
    pop['partition'] = pop['sub_id'].apply(lambda s: 'train' if s in [f'sub0{i}' for i in range(1, 8)] else ('val' if s == 'sub08' else 'test'))
    for part in ['train', 'val', 'test']:
        p_sub = pop[pop['partition'] == part]
        pca_p = p_sub[p_sub['method'] == 'Spatial_PCA_4ch']['f1'].mean() * 100
        unet4_p = p_sub[p_sub['method'] == 'Deep_UNet_4ch']['f1'].mean() * 100
        unet1_p = p_sub[p_sub['method'] == 'Deep_UNet_1ch']['f1'].mean() * 100
        print(f"  {part.upper():5s} ({len(p_sub)//9} records): Spatial PCA={pca_p:.2f}%, Deep U-Net 4-Ch={unet4_p:.2f}%, Deep U-Net 1-Ch={unet1_p:.2f}%")
        
    # 4. Partition Invariance Check
    pca_df = pop[pop['method'] == 'Spatial_PCA_4ch']
    c_mean = pca_df.groupby('case_id')['f1'].mean().mean() * 100
    s_mean = pca_df.groupby('snr_db')['f1'].mean().mean() * 100
    print(f"\n[Partition Invariance Check] Condition Mean={c_mean:.4f}%, SNR Mean={s_mean:.4f}%")
    assert abs(c_mean - s_mean) < 1e-3, "Partition invariance violated!"
    
    print("\nALL CONSISTENCY AUDIT CHECKS PASSED PERFECTLY!\n")

if __name__ == '__main__':
    check_all()
