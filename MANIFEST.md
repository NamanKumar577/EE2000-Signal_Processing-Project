# Independent Verification Package Manifest

**Package Archive:** `fecg_fpga_audit_verification_package.zip`  
**Total Files:** 99  
**Uncompressed Footprint:** 7,549,136 bytes (7.20 MB)  
**Target Hardware:** AMD Spartan-7 XC7S50-1CSGA324C on RealDigital Boolean Board  
**Toolchain:** AMD Vivado Design Suite v2025.2 (Build 6299465)  

---

## Summary of Included Categories

| Category | File Count | Size (Bytes) | Description |
| :--- | :---: | :---: | :--- |
| 1. Synthesizable RTL | 17 | 166,583 | See detailed file list below |
| 2. Build & Constraints | 12 | 2,215,154 | See detailed file list below |
| 3. Verification | 29 | 1,843,513 | See detailed file list below |
| 4. Hardware Evidence | 5 | 87,671 | See detailed file list below |
| 5. Implementation Reports | 15 | 753,549 | See detailed file list below |
| 6. Python Reference Sources | 12 | 214,839 | See detailed file list below |
| 7. Dataset Provenance | 9 | 2,267,827 | See detailed file list below |

---

## Complete Itemized File Inventory and Cryptographic Checksums (SHA-256)

| Category | Relative File Path in ZIP | Size (Bytes) | SHA-256 Hash |
| :--- | :--- | :---: | :--- |
| 1. Synthesizable RTL | `fpga_implementation/rtl/adaptive_detector.v` | 7,784 | `e1a439fe717cd48b032f88336473af2c0866301d3ad5f6ec4e35746b120e080b` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/bandpass_config_c.v` | 8,291 | `a09aceeacfd93f7907ea7c81ef0c27ad00c57398a11c3d5897e5960cc85f68c8` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/biquad_df2t.v` | 11,150 | `6cc89cff221cb25ff3ec38c27cdfe6b2ea5cea28a92ee423af6a6c7881ba9cc9` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/fecg_multichannel_top.v` | 33,505 | `03d9b3207b62f5dd7a6ca2042ce6235186177007d54ce88a4306d5f68c21fd27` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/fecg_single_channel_top.v` | 14,289 | `72d61243c343e7455277e0df1d98973949da7610611df2d753977c86de788499` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/fhr_calculator.v` | 18,637 | `4a32cceeeb6d972b051889b55b7a19732e58235d8c8e0c65941c9f74e630db5c` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/fhr_lut_rom.mem` | 1,506 | `031e022b59026cbdc1e437c76c50a91ac7919236441852fe17534717c86e50df` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/hp1_baseline.v` | 7,735 | `98daa86eed9a0a36e765f4ed026e0c572b20f70d62817cc6f077b218dc2cd8a1` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/interval_fusion.v` | 13,267 | `16ea7b83c84211f52f4a0fa4999e5cc8fdbaa35fe755dd097295d68291140392` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/lp40_filter.v` | 4,855 | `a5b38fd038caaf382f6f984bb94d636fdca9601d4f3554d18499c546ca883ec4` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/peak_localizer.v` | 8,259 | `52a3518b9940808bbb6aba366ff16071ef6ff166e64390012fc2a6307cfc82bd` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/spatial_beamformer.v` | 6,851 | `383fe54a7ddf399b02bdca7f87b83515888fac297ec2b0afed49662f9a79f5f4` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/squarer_mwi.v` | 5,950 | `1efb91e240d02f77c39c3494beb0a1a85129f25df20acafe156c6be22434f9ba` |
| 1. Synthesizable RTL | `fpga_implementation/rtl/weight_slew_engine.v` | 6,876 | `efe8d3aad39424a40f5662b11c895e53d7cf196c6df87c5711f55376b271edab` |
| 1. Synthesizable RTL | `uart_bringup/rtl/uart_rx.v` | 5,924 | `67fd699561b9b8c8c4a8f2248cce7135b6e8bbd89f8f33c1fbe0c7a01b63b49e` |
| 1. Synthesizable RTL | `uart_bringup/rtl/uart_tx.v` | 5,019 | `c666db95d60d4d6cb6a4e8e703e01aad021ae5c09de55a0facf66d5fbc223c9d` |
| 1. Synthesizable RTL | `uart_bringup/rtl/uart_top.v` | 6,685 | `2db30bdcbfec80922a825a4bd0b063d5236a9e9433347de901e4a4880bf5b9b2` |
| 2. Build & Constraints | `fpga_implementation/constraints/boolean_multichannel.xdc` | 3,138 | `b042e9e9cdf52ad569f53f268d362752b6bb6044a159b8cf2e8230db80edfe41` |
| 2. Build & Constraints | `fpga_implementation/constraints/spartan7_timing.xdc` | 1,289 | `a0fcfad016f05488ab1e5a43a2e049973b9df2d94cc84854763fe112a5000317` |
| 2. Build & Constraints | `fpga_implementation/reports/build_multichannel_bitstream.tcl` | 3,530 | `82ca693514b838d75b27035a86289bb708a3e671078db728bcaa88652806ad3e` |
| 2. Build & Constraints | `fpga_implementation/reports/program_multichannel_hw.tcl` | 933 | `a66f77c21d601a3eb21ae79b39fefe3a75f295fdc165e9f1d92032258abf3597` |
| 2. Build & Constraints | `fpga_implementation/reports/check_hw_device.tcl` | 738 | `bb1cde3fa4d41d984109a99de1de25ea5d62ad18e3927f812b2daf9f041a131c` |
| 2. Build & Constraints | `fpga_implementation/reports/run_synth_impl.tcl` | 2,693 | `5d1cbbddc9c2230e97e40ccc84d4b80d6e47b52904b1d7ce597ac09c5973189b` |
| 2. Build & Constraints | `uart_bringup/constraints/boolean_board.xdc` | 4,052 | `961ee74271bf7b7d9e5f2101b02b2ee8ff6c41ed1dff8d8d852c2a85d9fbe05f` |
| 2. Build & Constraints | `uart_bringup/scripts/check_hw.tcl` | 463 | `bd235e355683f61c486d492e1f3ea970c5b3318c5b365731df91357056c283e1` |
| 2. Build & Constraints | `uart_bringup/scripts/program_hw.tcl` | 518 | `aca90348003eca5f4fa4853ef666d1b92c82f73167543aefc6c0b60e4edd22dd` |
| 2. Build & Constraints | `uart_bringup/scripts/run_production_build.tcl` | 4,093 | `903830a5bba8693d95c14f8de565f78b6e9a3d00c265d6c915f71993909ae2aa` |
| 2. Build & Constraints | `fpga_implementation/bitstream/fecg_multichannel_top.bit` | 2,192,145 | `503abc132ee4614f8868f2aca74cca0b0a396f90607d6356f17ae537f753023f` |
| 2. Build & Constraints | `fpga_implementation/build/VIVADO_VERSION.txt` | 1,562 | `284583139fad4ea08b4d545ce305faa89774c5f48895b7415f1037cf9181f9cb` |
| 3. Verification | `fpga_implementation/testbenches/unit/tb_adaptive_detector.v` | 5,024 | `e26cc36427c531e173438fae0b79e05ff3d772d2321cc08b392d2a698771ae25` |
| 3. Verification | `fpga_implementation/testbenches/unit/tb_bandpass_config_c.v` | 3,928 | `8339929c6d9ac9c438bb4394bdc464f6afa373ab7e4acb4fbbaf37836e24475a` |
| 3. Verification | `fpga_implementation/testbenches/unit/tb_biquad_df2t.v` | 10,532 | `8fac6336a6ca95abfdeb921653fcd8fba6a3652979dfda85d01cfa9cbda03916` |
| 3. Verification | `fpga_implementation/testbenches/unit/tb_fecg_single_channel_top.v` | 6,663 | `3c4f8145007bbc47841ff682b27cfdbc02a94688b8df8e7b31ff9e6f86531c79` |
| 3. Verification | `fpga_implementation/testbenches/unit/tb_fecg_single_channel_verifier.v` | 5,303 | `3e30d80f33821b05f2d2673947112f06ac4a9c3c18d80f3aacc59fb76a9bbe4d` |
| 3. Verification | `fpga_implementation/testbenches/unit/tb_fhr_calculator.v` | 5,280 | `edb9e433f5ab24f79bf50692f66a92d9a711c39055fd9decc5041fca55464415` |
| 3. Verification | `fpga_implementation/testbenches/unit/tb_hp1_baseline.v` | 9,355 | `1c5eff0f95e122ed9a8e294d9d75efd15896b61fe780d1ac461cd5f810e3a694` |
| 3. Verification | `fpga_implementation/testbenches/unit/tb_interval_fusion.v` | 6,996 | `4786a65ebd1bd4e1b9e7cc4590b6e768a4389a24d0a2d7fc3f012b0aa436ae05` |
| 3. Verification | `fpga_implementation/testbenches/unit/tb_lp40_filter.v` | 3,944 | `91942f2d2f45610fea62442814ad2a000199a3507f5c822b6d74b45d66b04697` |
| 3. Verification | `fpga_implementation/testbenches/unit/tb_peak_localizer.v` | 4,712 | `bea3cc9c525fecf11863e141007f6be7b7fadb07fe9c8fc4874807abac41bae0` |
| 3. Verification | `fpga_implementation/testbenches/unit/tb_squarer_mwi.v` | 5,276 | `2b6e7f2603c6459a9decfc40f0b49007266bc0b44f3055ba015513077e37c7af` |
| 3. Verification | `fpga_implementation/simulation/run_vivado_golden_verification.py` | 8,595 | `75f5c86b9f99d14e4aa593a24d1c81619c55e56f18842adad3831d06521eede5` |
| 3. Verification | `fpga_implementation/simulation/verify_biquad_df2t.py` | 10,558 | `b6e54e0155d6671352a4e8f38dd2560f30f0482c2a7a28233cc1a0f86fea2536` |
| 3. Verification | `fpga_implementation/simulation/verify_hp1_baseline.py` | 9,861 | `58c1d3cd15a2bf1dcc6378956c8c2fb21275692d1e331a8a48375fcd209b7157` |
| 3. Verification | `fpga_implementation/simulation/verify_pca_fixed_point.py` | 23,869 | `8e01952a6b385a044b6c1a249b558c4e0ca58d0375741aff10809a1c92fcc422` |
| 3. Verification | `fpga_implementation/simulation/verify_phase1_submodules.py` | 19,288 | `7135599e6e8eb7ac9998ad53b0fa6f60fb79e2ac23b721d03489ae70c3e07071` |
| 3. Verification | `fpga_implementation/simulation/verify_single_channel_pipeline.py` | 12,797 | `dfa8992ef642cf80db63e26fa9097396adab8aa691d2e0be911906d762bd36b4` |
| 3. Verification | `verification/scratch/simulate_fhr_audit.py` | 15,314 | `53898247f236da2b300293b4709f9160d33e122648ece69cd7eb43fbcd981f81` |
| 3. Verification | `verification/scratch/test_filter_continuity.py` | 14,044 | `5d0b8d48d77e438f4a8b48bec0690b4a2ccc13c7f881ca3db847c0968bfbfab8` |
| 3. Verification | `verification/scratch/test_maternal_metrics.py` | 11,194 | `951d4577ee862cd89e609886b4cd298484c68e2e7d661fc175ee2f231b61bef1` |
| 3. Verification | `verification/scratch/filter_continuity_proof.png` | 617,673 | `9527bad67f17bb6bff29f4c7afebbe2d249f60e3de21bda1f59df2ba95f9e8d9` |
| 3. Verification | `verification/scratch/fhr_detection_audit_comparison.png` | 686,310 | `486699d6c3267e390f0d2485e863b36dfe295afcc21898e08c07185deca484fd` |
| 3. Verification | `fpga_implementation/simulation/vivado_sim_out/xelab.log` | 1,269 | `4837e981b2716b5aaddfbc16b9be554c8a804e39dd81e07e6a0fd78fcf9c63d4` |
| 3. Verification | `fpga_implementation/simulation/vivado_sim_out/xsim.log` | 1,547 | `67f73955556d169ad858a998cbeeadc81a703b2ea4484bd2ae72d3c868730539` |
| 3. Verification | `fpga_implementation/simulation/vivado_sim_out/xvlog.log` | 1,982 | `1f65da8101b9fd88f6c103c50f0b03ed2eef8e1e83eae14879010ccfa79235a2` |
| 3. Verification | `fpga_implementation/simulation/vivado_sim_out/vivado_events_out.txt` | 2,193 | `8af69a21a203219fd766b5b201d4a42b808661697fec71efb4b0fe11f299a711` |
| 3. Verification | `fpga_implementation/simulation/vivado_sim_out/vivado_waveform_out.txt` | 310,000 | `771753be934117a5fbd2503b79afb61e53c1eda0e3175ea0d0308c31c8c44b1c` |
| 3. Verification | `fpga_implementation/simulation/vivado_sim_out/stimulus_adc.hex` | 30,000 | `c1782d17fc96984809bfdfe195e3be159b1a8ed5d3eca40c2c4a8e2a3426c47b` |
| 3. Verification | `fpga_implementation/simulation/vivado_sim_out/stimulus_count.txt` | 6 | `c14f0eeaec609582c1564d5ad140795a7b7bbc9a3fa6e68b6d62fe34057cf2af` |
| 4. Hardware Evidence | `hardware_evidence/logs/task-1614_physical_fpga_com5_validation_6cases.log` | 2,115 | `e265f438ed1cb762099786bab3fe8ed4601b98da0c82639909302b43be0fb97e` |
| 4. Hardware Evidence | `hardware_evidence/logs/task-1409_physical_fpga_com5_qrs_telemetry.log` | 1,096 | `760367349a6d033a23615458e4999787372062999944d6759ffdb85d0cd0e5eb` |
| 4. Hardware Evidence | `hardware_evidence/logs/task-1600_jtag_programming.log` | 2,778 | `87f1f8f097241463ce498bbff5765908eef98e017c0b0fa2b881b3a28a60516e` |
| 4. Hardware Evidence | `fpga_implementation/reports/vivado.log` | 80,571 | `3410175fa72a3151e689efc00015d690d6646ea1e02eb775defa3ab1df862088` |
| 4. Hardware Evidence | `fpga_implementation/reports/vivado.jou` | 1,111 | `556018690bc511072e28f16a041c16d65a86ef5d3b55b50a8732df10d41feefa` |
| 5. Implementation Reports | `fpga_implementation/reports/multichannel_out/post_synth_utilization.rpt` | 9,033 | `7ad6c4474a84d21c666dc99013101bd976dcbeea616324fa884434c4c3941345` |
| 5. Implementation Reports | `fpga_implementation/reports/multichannel_out/post_synth_timing.rpt` | 30,621 | `106f10bc0852138693e544c31be524f1e2f941faad1bbff650224470930b134c` |
| 5. Implementation Reports | `fpga_implementation/reports/multichannel_out/post_place_utilization.rpt` | 11,223 | `0a6e607c130ce83ad4bf68055208bb80c122477126746cca2e205c7a028bafdb` |
| 5. Implementation Reports | `fpga_implementation/reports/multichannel_out/post_place_timing.rpt` | 30,733 | `4db9ec45428bb9b8dbf01c3b9acde7a2687b281d99a6c037806523bb6fd4b959` |
| 5. Implementation Reports | `fpga_implementation/reports/multichannel_out/post_route_utilization.rpt` | 11,217 | `57175a3b5fe089c9a3b7b22b027cc5aa493d172b79216b5891bcbd8b70087129` |
| 5. Implementation Reports | `fpga_implementation/reports/multichannel_out/post_route_timing.rpt` | 316,793 | `1b2907a32933b36ecba41152b3e31dd11d5de49879dcc30d32cf65de6293e6c0` |
| 5. Implementation Reports | `fpga_implementation/reports/reports_out/post_synth_utilization.rpt` | 8,635 | `baf6974be2d68a03bee8841f86bdf301deb9962beecb6efa1c62d5bfc6f6edb2` |
| 5. Implementation Reports | `fpga_implementation/reports/reports_out/post_synth_timing.rpt` | 24,697 | `48f0e4a61dd8dafbe8700bec6d2be9f6b452674fd77eac7bb303a93ed719a765` |
| 5. Implementation Reports | `fpga_implementation/reports/reports_out/post_place_utilization.rpt` | 10,589 | `1e2961f84eb8ea9b8deebf73f75e360635b95e519a42437cf74b4c0417755167` |
| 5. Implementation Reports | `fpga_implementation/reports/reports_out/post_place_timing.rpt` | 25,525 | `65310fac29e7df557e4adcf77df5d8092769fec51e22dfe0c1e84199d854541f` |
| 5. Implementation Reports | `fpga_implementation/reports/reports_out/post_route_utilization.rpt` | 10,819 | `ba36f3da01155d8626d62cab7675784db5c3c5a77213b250f17bc4777e37059d` |
| 5. Implementation Reports | `fpga_implementation/reports/reports_out/post_route_timing.rpt` | 194,621 | `92f9d1ce58ad5412a56e833e5f6e80edf0e0084698ec73c60ff1b6d8eadd900c` |
| 5. Implementation Reports | `fpga_implementation/reports/phase2_phase3_hardware_report.md` | 20,629 | `e2491850ba16a98c323d2613dcc6bb730de8c6fee40927d015b1c6b88bf340ab` |
| 5. Implementation Reports | `fpga_implementation/reports/phase4_algorithmic_correctness_report.md` | 15,377 | `9eedbac38eb92629cf5ef699682fb92ec3450ff4f8960b3f6514974e7fe60319` |
| 5. Implementation Reports | `fpga_implementation/reports/phase5_performance_optimization_report.md` | 33,037 | `d3cdff875a9da7ba63c7d15d374f9c9b5d062ffcb27203bd2d3b1478b41f3130` |
| 6. Python Reference Sources | `src/causal_pipeline.py` | 16,599 | `6561a8cb71d68a49539e41cfedf70fc9b790d8160c1846165cfa2589c03bdc59` |
| 6. Python Reference Sources | `src/evaluation.py` | 9,952 | `f70fe58d83e35c92538eee4e9c0703c4219ef3e2ac3f1cc2fc26f78200eeb7e6` |
| 6. Python Reference Sources | `src/fhr.py` | 8,305 | `13f4e7f1ce6f11d4a3f1d54d78bc2efd0ae3098a6d23d7633dea853c7b9ee729` |
| 6. Python Reference Sources | `src/fpga_int_model.py` | 19,863 | `31b0530dde5a1768156c8412c7071a93e575ce1f95d48d6e489fd47aedb6263b` |
| 6. Python Reference Sources | `src/fecg/hardware/bit_accurate_reference.py` | 25,877 | `964e08b32fbe9cfddc9f6fe273f326f45d6329d090225f75f5a89d323f5ebc8b` |
| 6. Python Reference Sources | `src/fecg/hardware/fpga_int_model.py` | 19,880 | `af3d1299538296534cfc9fee5b6692eb2067e2c9397b02d26853704172dc969c` |
| 6. Python Reference Sources | `src/fecg/pipelines/causal_pipeline.py` | 16,605 | `63a57bc1e5b502a11c8a6d3c390c4e013e17c788b30b6bb815023e49da55798c` |
| 6. Python Reference Sources | `src/fecg/detection/fhr.py` | 14,131 | `51e72a795580c6638fd902d86ed3eacae86cbdd3b4b1ebcffb08a0b160e1ef1a` |
| 6. Python Reference Sources | `src/fecg/core/evaluation.py` | 9,963 | `b5c5c2f8e6d8b74bfe73f4b726cb37e3b3ea4dd528203f4883b84afd4692c1b8` |
| 6. Python Reference Sources | `fpga_implementation/uart_host/validate_real_datasets.py` | 24,826 | `b2636f92d350a06977e4c3d49a76a27cc4df60934e8bc578d46dd7aece16d8fb` |
| 6. Python Reference Sources | `fpga_implementation/uart_host/fecg_uart_client.py` | 40,466 | `0f2d602217ce697b0f9cdd6b302d2d4267c5e9ba80a99a8e8d83da2be1200eb2` |
| 6. Python Reference Sources | `scratch/run_expanded_validation.py` | 8,372 | `948c1a17e8e79217da48fd374b18406679f7027dba6b5faed810ff1fbafd469f` |
| 7. Dataset Provenance | `data/FECGSD/DESTINATION/ANNOTATORS` | 36 | `b07d54f11dc4400a3d8983af17fdad73e278a6dc7802c93833762313316b6279` |
| 7. Dataset Provenance | `data/FECGSD/DESTINATION/RECORDS` | 280,000 | `ab0e0e8f0a982af2539d0c97f011189b75931be031754e51a7115b4075f79748` |
| 7. Dataset Provenance | `data/FECGSD/DESTINATION/SHA256SUMS.txt` | 1,931,818 | `81ebd5ec9f45546977809916877ef9ed59f0fb30f1cd5b9494443391a255e413` |
| 7. Dataset Provenance | `data/FECGSD/DESTINATION/sub01/snr00dB/sub01_snr00dB_l1_c0_fecg1.hea` | 2,520 | `5bc735173d4e0d7d4f929b92a930e77560668b92103bbb1801811ca97bac59d2` |
| 7. Dataset Provenance | `data/Non-Invasive_Fetal_ECG_Arrhythmia_Database/DESTINATION/HEADER.shtml` | 2,464 | `35b89299e873d50dac9070569896114d8b685852fa8881ed4fc303e3e72d53b7` |
| 7. Dataset Provenance | `data/Non-Invasive_Fetal_ECG_Arrhythmia_Database/DESTINATION/RECORDS` | 168 | `cf56618f7a6f00cdd12edd7b2d0250650bffc6d42655e664eafb3baa0c0abd0e` |
| 7. Dataset Provenance | `fpga_implementation/reports/phase4_real_dataset_results.csv` | 2,064 | `38820b0e939cd7a1ce7388a96a09f0d3a1a9fb2ded0a9dce483674e948920bbd` |
| 7. Dataset Provenance | `fpga_implementation/reports/phase5_expanded_fecgsyndb_results.csv` | 42,112 | `30f1fd2d155a4e32de4a113377fbfc8b2b62f4f1845a1a8e6ffeed323bd3e312` |
| 7. Dataset Provenance | `docs/DATASET_PROVENANCE_AND_ANNOTATIONS.md` | 6,645 | `3ebffdedea06b5425c007daa7985fb15ec8ae6dda88d20b40ee52e35d6d3b787` |
