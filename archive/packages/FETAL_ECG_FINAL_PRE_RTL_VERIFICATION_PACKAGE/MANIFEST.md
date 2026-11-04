# Final Pre-RTL Verification Package Manifest and SHA-256 Checksums

**Total Files:** 110

| Relative Path | Size (Bytes) | SHA-256 Checksum | Description |
|---|---:|---|---|
| 01_fixed_point_scaling/FIXED_POINT_EQUIVALENCE_FINAL.csv | 522 | 054115970af24193df5725ac38ea70c9d11920d2bac0cd0b42d5cc1e01ff4311 | Priority A: Scaling audit, SQNR recalculation, and stage error |
| 01_fixed_point_scaling/FIXED_POINT_SCALING_AUDIT.md | 3,359 | bdf0fad8f9055cdd0ec0334913d140dbe69dc26e33d7e9e80e6cba2f98b34468 | Priority A: Scaling audit, SQNR recalculation, and stage error |
| 01_fixed_point_scaling/FIXED_POINT_SCALING_CORRECTED.csv | 3,416 | 5bfc032ea9e3d1b9c0fc53e6c69bb1861135a0ca00bc48d1eac400aa9a758b5a | Priority A: Scaling audit, SQNR recalculation, and stage error |
| 01_fixed_point_scaling/FIXED_POINT_STAGE_ERROR.csv | 8,465 | 24b746b1111c3b4c6ac74cbd6f5a5bed9de284b97e433d36e46c2be9e6ce37d8 | Priority A: Scaling audit, SQNR recalculation, and stage error |
| 01_fixed_point_scaling/scripts/run_fixed_point_scaling_audit.py | 19,952 | 17afdb3c678ef3335ed64850836fbb5b8dfe1bed45d2a1eee9c22348ff6ded37 | Priority A: Scaling audit, SQNR recalculation, and stage error |
| 02_hardware_arithmetic/DATAPATH_WIDTH_SPEC_FINAL.md | 6,435 | be7ce1539e499ebc42f26a52f6103ea00ca9e5dfeff5d987e4ad02db17208990 | Priority B: Datapath width spec, overflow accounting, integer LUT |
| 02_hardware_arithmetic/FHR_INTEGER_LUT.csv | 6,167 | 7a543b9406a3ca14952ca82cf535cc866c9f88cd43c7e7d8ca1cc8df51d5cda9 | Priority B: Datapath width spec, overflow accounting, integer LUT |
| 02_hardware_arithmetic/HARDWARE_ARITHMETIC_AUDIT.md | 5,821 | fa544f96b5654720cbbb722df74977d0aa86604cfe4174344e35291620d42dca | Priority B: Datapath width spec, overflow accounting, integer LUT |
| 02_hardware_arithmetic/OVERFLOW_ANALYSIS_FINAL.csv | 1,918 | 6504037d952adac2529910269355ad51f7cf50d38d12bdf65b5bc7cd804d5235 | Priority B: Datapath width spec, overflow accounting, integer LUT |
| 03_fhr_reconciliation/FHR_AGGREGATE_RESULTS.csv | 444 | 299025c7c1683805d8a21144610309bebfbc18fa344c53a0c7508b4db470d44f | Priority C: Causal FHR regenerated benchmarks and alignment audit |
| 03_fhr_reconciliation/FHR_CONDITION_ANALYSIS.csv | 643 | 56ed3692fedf1a266807bcf3ad23897db2d23ee50d7d04d11186ed72ef50f064 | Priority C: Causal FHR regenerated benchmarks and alignment audit |
| 03_fhr_reconciliation/FHR_METRIC_RECONCILIATION.md | 4,858 | 013c92571578288e3d8f77e7fd7035669b7b6fd50aa065e9a83a6ca44783071b | Priority C: Causal FHR regenerated benchmarks and alignment audit |
| 03_fhr_reconciliation/FHR_REFERENCE_ALIGNMENT_AUDIT.md | 1,965 | 714ab0cf3ff03b661fa1b6c5b6b1af4d7066e61fa0b4a95b2c7c039975b95431 | Priority C: Causal FHR regenerated benchmarks and alignment audit |
| 03_fhr_reconciliation/FHR_RESULTS_REGENERATED.csv | 30,073 | c537cc358a800ea44908a928269d770ee0ab3c47bf9111f3fe2085a8793c9a82 | Priority C: Causal FHR regenerated benchmarks and alignment audit |
| 03_fhr_reconciliation/scripts/run_fhr_reconciliation_audit.py | 20,149 | 536ab6da9146ca76e216be8852ea746f2433f879aa5823ccea96a1ee2f977ac9 | Priority C: Causal FHR regenerated benchmarks and alignment audit |
| 04_calibration/CALIBRATION_AVAILABILITY_FINAL.csv | 305 | 3a4ad0bd2317b24d7c710352d5431706e877b1b5f3d01f86d0a602578485f46e | Priority D: Disentangled metrics, cold start spec, availability |
| 04_calibration/CALIBRATION_COLD_START_SPEC.md | 2,338 | e21e57722809b404b71257d8d02855288f20311326abc0b97690dda0e4848ac8 | Priority D: Disentangled metrics, cold start spec, availability |
| 04_calibration/CALIBRATION_METRIC_DEFINITIONS.md | 2,853 | b3bdcbbb39782c3fb9fa2de4cf0e55ce2b1b42cb9764e46d47a26f4413c82e03 | Priority D: Disentangled metrics, cold start spec, availability |
| 04_calibration/CALIBRATION_METRICS_CORRECTED.csv | 27,103 | 4dd3c9a30996f5ed0530497152955b8a91d6456002a56e9d473f5718391627e6 | Priority D: Disentangled metrics, cold start spec, availability |
| 04_calibration/CONTINUOUS_RECALIBRATION_RESULTS.csv | 2,370 | c3f4398048b759900a1e947ef2ce05615a233bca9c9bb0c43c1df35502b3ae37 | Priority D: Disentangled metrics, cold start spec, availability |
| 04_calibration/scripts/run_calibration_audit.py | 16,703 | 7301edc3f167d873d35e2fa4a756334b0ac26090a468968a1cb210feafe23b12 | Priority D: Disentangled metrics, cold start spec, availability |
| 05_filter_timing/FILTER_DELAY_AUDIT.md | 3,227 | 3ba2ba1fb89345c4dff2879d4315968b7ab584b33faed65ab2a7960bf8a27d93 | Priority E: Group delay calculations and 18-sample latency rewind |
| 05_filter_timing/FILTER_GROUP_DELAY.csv | 3,340 | 0dc2eef26136e65ba25f0baca40802e884d3297f61ab6c0aae3340cd8ff1fd42 | Priority E: Group delay calculations and 18-sample latency rewind |
| 05_filter_timing/QRS_TIMING_COMPENSATION_RESULTS.csv | 7,347 | 4015dc1aa5a468fead0ea92156886745a327afbdd6ed642c80d378beb05ca10c | Priority E: Group delay calculations and 18-sample latency rewind |
| 05_filter_timing/tests/run_filter_delay_audit.py | 11,988 | 5cd295ef8b37d5d801b8344f94983cef837b947ea58fbbc7914e7ca4d4400acd | Priority E: Group delay calculations and 18-sample latency rewind |
| 06_calibration_update/CALIBRATION_WINDOW_FINAL.md | 2,348 | 122f6e53bc947395884a9e5d91778f3d57c1c3c45414a1dfa467d64d027b6198 | Priority F: 4s vs 10s window evaluation and 64-sample slew engine |
| 06_calibration_update/WEIGHT_UPDATE_SPEC_FINAL.md | 2,784 | 6547c46c6c8fb8cb3cda17a366d380b843e89cc22b2b630e484e32ac35f5dd25 | Priority F: 4s vs 10s window evaluation and 64-sample slew engine |
| 07_uart/CALIBRATION_PROTOCOL_SPEC_FINAL.md | 1,657 | 3a812f8fa25a0635622e42a97b978b3d49f8ae1bfc11acdb884fc48b9699e1cd | Priority G: UART packet protocol, status byte, and CRC8-CCITT |
| 07_uart/UART_PACKET_IMPLEMENTATION_FINAL.py | 10,321 | 6c37477ce9d567b4ba8325c53320a47f46e2a63ef65a11ee434041ba5e1a5e2e | Priority G: UART packet protocol, status byte, and CRC8-CCITT |
| 07_uart/UART_PROTOCOL_SPEC_FINAL.md | 3,706 | d2cdc184fe7ed606eaa520e5579d35d328fcda6aa70483b3e05914e369c86ebf | Priority G: UART packet protocol, status byte, and CRC8-CCITT |
| 07_uart/UART_STATUS_BYTE_FINAL.md | 3,019 | 1ff97f56561d0e39c6c77b9abb71c0284e5b96f4267f00f181b107b5f1254cae | Priority G: UART packet protocol, status byte, and CRC8-CCITT |
| 08_benchmark_coverage/BENCHMARK_COVERAGE_FINAL.md | 3,990 | 5676e7c60f5a195832582b1c2038f0b3dd6dc4c4ed542eaf87818d89b3938252 | Priority H: Forensic investigation of 4 missing benchmark records |
| 08_benchmark_coverage/MISSING_RECORDS_FINAL_AUDIT.csv | 851 | be9a96fa0281f86eb8f9a6b824737539812438e6d2dfef74ffdd872fd6b982b2 | Priority H: Forensic investigation of 4 missing benchmark records |
| 09_final_specification/CROSS_DOCUMENT_CONSISTENCY_AUDIT.md | 4,606 | 47569c90563cf0684566c994d2e0587da9a3a8e76bf28e72dfb4d0b57c80c4a7 | Priority J: Master parameter JSON, cross-document audit, architecture |
| 09_final_specification/FINAL_ALGORITHM_SPEC.md | 4,570 | 66ce2caafec92a1d63d784a6e5eb09ae45562d7bde1a9f391ebd1bfd95c6a7b7 | Priority J: Master parameter JSON, cross-document audit, architecture |
| 09_final_specification/FINAL_FIXED_POINT_SPEC.md | 2,661 | 7f30d2ee978d0cbe0526978addb2d1159527fad2450d7eea0e31ea2b36c23421 | Priority J: Master parameter JSON, cross-document audit, architecture |
| 09_final_specification/FINAL_FPGA_ARCHITECTURE_SPEC.md | 3,126 | 7865337c0f1e074224fd6ee3ef820ba088b739fad45f7e199bea47a1e6e1eee3 | Priority J: Master parameter JSON, cross-document audit, architecture |
| 09_final_specification/FINAL_HARDWARE_PARAMETERS.json | 4,141 | a8a07a6bf587602269e697fe250b7c6035e73bf80b757913fcb02529a7d73c81 | Priority J: Master parameter JSON, cross-document audit, architecture |
| 09_final_specification/PARAMETER_USAGE_MAP.csv | 5,206 | 860d1e5677a97d75b908587d94235be561d84555222f46b16f9bb5724bae092d | Priority J: Master parameter JSON, cross-document audit, architecture |
| 10_regression/__pycache__/conftest.cpython-313-pytest-9.2.0.pyc | 1,537 | 59c87fa76f7bd160c757d6adfe50352603d2481bf81e709670441f97ac733ac7 | Priority K: Self-contained regression test suite and runners |
| 10_regression/conftest.py | 723 | b8808d79eb770b08b5a84ad99d8f53e0e63c2804b04ffc144eb35c147b4f0130 | Priority K: Self-contained regression test suite and runners |
| 10_regression/requirements.txt | 244 | d4605ac0653e11be91eb2b0983129bb7b0da122fc94c122873b30dce527c3cc0 | Priority K: Self-contained regression test suite and runners |
| 10_regression/run_all_experiments.sh | 1,752 | d6218b70f1d2030c8a20ba8aea7018e2efee7f373532046cb39fb789fc8eb534 | Priority K: Self-contained regression test suite and runners |
| 10_regression/run_all_tests.sh | 1,910 | bf010954495ee5fa025e9823c6730ff87586b2f68a55e199c0f6024a19f188bf | Priority K: Self-contained regression test suite and runners |
| 10_regression/TEST_EXECUTION_REPORT.md | 3,855 | d0f2edbb64eb9bad54ecf174f55c006b0088d1855f31de8ecde0432155c5f5bd | Priority K: Self-contained regression test suite and runners |
| 10_regression/test_results.txt | 11,126 | bfcec4098f7b487d14f5cb5d0c4f4db7ff6221c8f504a35e5a7bb264e0797a80 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/__pycache__/test_calibration_confidence_and_recalibration.cpython-313-pytest-9.2.0.pyc | 12,114 | 3934d2eea339b13f02175ba6f763489b0589ada422a11815859903d6f9d82ee8 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/__pycache__/test_end_to_end_pipeline_synthetic.cpython-313-pytest-9.2.0.pyc | 21,489 | a50002bcd650c4cbd5b0ca381db2d87c26276e11f3c8da2066264d5af8ad6f56 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/__pycache__/test_fhr_interval_fusion_and_median5.cpython-313-pytest-9.2.0.pyc | 16,894 | 2cb1216a3aaaeef72b1a6ba93f36a66f32ec8cf9e420c69fce29ef37e968b571 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/__pycache__/test_filter_coefficients_exact.cpython-313-pytest-9.2.0.pyc | 6,921 | 1df02ba211881379f6f4bb60a2bbb5717b1f628ce7d42978f7f693bff8337a55 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/__pycache__/test_filter_delay_and_timing_compensation.cpython-313-pytest-9.2.0.pyc | 9,824 | bd94242cb8d8e12de5e78df5fe2518c53f9ef2276583c92839307374eb5b27dc | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/__pycache__/test_fixed_point_scaling_exact.cpython-313-pytest-9.2.0.pyc | 7,771 | 2350a52741d7c48d1f7b40751fcd3f6a64bad7b085b9159c8137fb54f3471476 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/__pycache__/test_hardware_arithmetic_exact.cpython-313-pytest-9.2.0.pyc | 26,380 | cd6a561a0efd020aab2851f2f31d5579023417e8b18e73af6e2bc2755931d5ef | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/__pycache__/test_qrs_matching_strict.cpython-313-pytest-9.2.0.pyc | 15,995 | 224ddf46d7f946af9f46afdf6dea107c26c0b47c406685e1bbd38bc2a5be1a40 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/__pycache__/test_uart_protocol_final.cpython-313-pytest-9.2.0.pyc | 16,478 | 0ec657115f9ef88384b17e631fe7dc2080be94d1c46d479d332f08ead7dea79e | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/__pycache__/test_weight_crossfade_slew.cpython-313-pytest-9.2.0.pyc | 7,352 | 4b45bc083c1df9cb823ec131e36fc2ef37b3f829e7eedb363f56a6852511e98e | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/test_calibration_confidence_and_recalibration.py | 3,008 | 7ff721abc3da910fe28a1b68ad0a858b9d8f7909307fcfd014201bbb5c7b12fa | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/test_end_to_end_pipeline_synthetic.py | 4,750 | 6b03db4dd7deb3319d8da0750c8d16f4c8592a5fdb35dc7ff7436a77ee77b1b7 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/test_fhr_interval_fusion_and_median5.py | 4,033 | a079cff8535888349799585af83cac1c582d470a4555983a9d8e03a4b43f33fd | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/test_filter_coefficients_exact.py | 2,071 | 7b7be6e9f9393e77b1f585f0e2bf7ba63d9cfc56eb9009846b8d23e9df65e8b6 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/test_filter_delay_and_timing_compensation.py | 2,599 | 305cd206e0fca663ba069fa034edb972f5f758f6b4ff45540a19d4fc72a7f571 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/test_fixed_point_scaling_exact.py | 2,677 | 7c8a39890005cf290594ebb138e94924dbaee221308d13df0fadf773920b4bb0 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/test_hardware_arithmetic_exact.py | 3,674 | d7b38c0f5f1edef2fcaa63ca628f63febd358667e1c60d2793bface07924965a | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/test_qrs_matching_strict.py | 3,685 | 8a3ed59c210fd227525e08a119960b8060325adf5545a067998a4eb6df1ef1c5 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/test_uart_protocol_final.py | 3,493 | d34196719a8f5e9b2e2f93fe6f4be5e015aef7978dbd8a0d80a05fb5c61bfeb6 | Priority K: Self-contained regression test suite and runners |
| 10_regression/tests/test_weight_crossfade_slew.py | 2,935 | 29074bb792d479fa62dc01d4b4b9d6637ac0f76a878fb98f653c318f8f2f1ae1 | Priority K: Self-contained regression test suite and runners |
| 11_source_code/baseline/causal_pipeline.py | 16,599 | 6561a8cb71d68a49539e41cfedf70fc9b790d8160c1846165cfa2589c03bdc59 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/baseline/fpga_int_model.py | 19,863 | 31b0530dde5a1768156c8412c7071a93e575ce1f95d48d6e489fd47aedb6263b | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/corrected/src/__init__.py | 552 | 57b763c868484a9ddc50efa320e0cdff98c6941f67c56f5d18f09907ed2fe3e4 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/corrected/src/__pycache__/__init__.cpython-313.pyc | 267 | b29d1dd539107a4cb697bfaff7ecee825fb26631b04c6517a490b349c9b7bb3a | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/corrected/src/__pycache__/fhr.cpython-313.pyc | 7,732 | 0aaffeec29fd5792d7e80549c673a1bd19fec728a943c7e4eddbeda05d39de2b | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/corrected/src/bit_accurate_reference_model_final.py | 20,990 | 709f53c541f5d77a34e0fbd57f8ea25c794faa4befd60ea4c436ab845a691b59 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/corrected/src/causal_pipeline.py | 16,599 | 6561a8cb71d68a49539e41cfedf70fc9b790d8160c1846165cfa2589c03bdc59 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/corrected/src/data_loader.py | 10,811 | 7a8a0ad7349b0f5594196ed7ff1b40bc6f2f97796eca6a86943c1aee9a6b5e3a | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/corrected/src/evaluation.py | 9,952 | f70fe58d83e35c92538eee4e9c0703c4219ef3e2ac3f1cc2fc26f78200eeb7e6 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/corrected/src/fhr.py | 8,305 | 13f4e7f1ce6f11d4a3f1d54d78bc2efd0ae3098a6d23d7633dea853c7b9ee729 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/corrected/src/fhr_implementation_corrected.py | 5,487 | 812d6c65295a67ed8e29c8c3cf1deb1d77f0e808c2f843dc168e3efd7fb27cab | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/corrected/src/preprocessing.py | 7,644 | 36fa3470b9e3505b709ca3b266dd3c17f4fe3b589872bf4dd9b3d67a42234d04 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/corrected/src/qrs_detector.py | 10,307 | a69ddd335e50c64004e993c3032b4399dc3dca2e074fecec25fe1025bca7ffc0 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/corrected/src/uart_protocol_final.py | 10,321 | 6c37477ce9d567b4ba8325c53320a47f46e2a63ef65a11ee434041ba5e1a5e2e | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/__init__.py | 552 | 57b763c868484a9ddc50efa320e0cdff98c6941f67c56f5d18f09907ed2fe3e4 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/__pycache__/bit_accurate_reference_model_final.cpython-313.pyc | 20,595 | d1229c043a313d447e5d5ffed474707016dee12d0e63d995f6ec3f31d8df7883 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/__pycache__/causal_pipeline.cpython-313.pyc | 21,318 | 0e7356a427c3e1f17021af798680a4bb775f64a44953ceca92ddec7aabe726da | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/__pycache__/evaluation.cpython-313.pyc | 10,234 | 48fc456ee6d025b75d769a741634b83f76f609615304b75c60be17375dbc124e | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/__pycache__/uart_protocol_final.cpython-313.pyc | 11,765 | 21fc3b37513e6a2ef2000599d83eb3c338bc259ed128a2821f3172740fa43b5c | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/bit_accurate_reference_model_final.py | 20,990 | 709f53c541f5d77a34e0fbd57f8ea25c794faa4befd60ea4c436ab845a691b59 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/causal_pipeline.py | 16,599 | 6561a8cb71d68a49539e41cfedf70fc9b790d8160c1846165cfa2589c03bdc59 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/data_loader.py | 10,811 | 7a8a0ad7349b0f5594196ed7ff1b40bc6f2f97796eca6a86943c1aee9a6b5e3a | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/evaluation.py | 9,952 | f70fe58d83e35c92538eee4e9c0703c4219ef3e2ac3f1cc2fc26f78200eeb7e6 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/fhr.py | 8,305 | 13f4e7f1ce6f11d4a3f1d54d78bc2efd0ae3098a6d23d7633dea853c7b9ee729 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/fhr_implementation_corrected.py | 5,487 | 812d6c65295a67ed8e29c8c3cf1deb1d77f0e808c2f843dc168e3efd7fb27cab | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/preprocessing.py | 7,644 | 36fa3470b9e3505b709ca3b266dd3c17f4fe3b589872bf4dd9b3d67a42234d04 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/qrs_detector.py | 10,307 | a69ddd335e50c64004e993c3032b4399dc3dca2e074fecec25fe1025bca7ffc0 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/reference_model/uart_protocol_final.py | 10,321 | 6c37477ce9d567b4ba8325c53320a47f46e2a63ef65a11ee434041ba5e1a5e2e | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/tools/reconcile_qrs_metrics.py | 16,074 | 4807c319bcbdae018ca645bb47b5719fb96b25eee70f49b11bdd0d4da3cd28e8 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/tools/run_calibration_audit.py | 16,703 | 7301edc3f167d873d35e2fa4a756334b0ac26090a468968a1cb210feafe23b12 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/tools/run_fhr_reconciliation_audit.py | 20,149 | 536ab6da9146ca76e216be8852ea746f2433f879aa5823ccea96a1ee2f977ac9 | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/tools/run_filter_delay_audit.py | 11,988 | 5cd295ef8b37d5d801b8344f94983cef837b947ea58fbbc7914e7ca4d4400acd | Golden reference model, historical baselines, and audit scripts |
| 11_source_code/tools/run_fixed_point_scaling_audit.py | 19,952 | 17afdb3c678ef3335ed64850836fbb5b8dfe1bed45d2a1eee9c22348ff6ded37 | Golden reference model, historical baselines, and audit scripts |
| 12_execution_logs/commands.txt | 1,394 | 011b2a6ebac31b4bf2d56ffa13acc206c567e26b0b4afe5211f2b941f16b9f67 | Execution transcripts, command lists, and diagnostic logs |
| 12_execution_logs/environment.txt | 2,948 | b6837b3d7c7dca216d081b6a6d08b46ae856cab3974d2094584b549d33e31fa8 | Execution transcripts, command lists, and diagnostic logs |
| 12_execution_logs/execution_log.txt | 3,720 | 10dd22bdb5725a96f5ffaaf37636ffb35bc5a385a0efc8a02d5f7773bfcccfe8 | Execution transcripts, command lists, and diagnostic logs |
| 12_execution_logs/failures_and_retries.md | 4,556 | 34bbc2c9d38ef2fdb7d43579a8eb326085f01fef7b09d7edc94757c5a20eb6ef | Execution transcripts, command lists, and diagnostic logs |
| __pycache__/conftest.cpython-313-pytest-9.2.0.pyc | 1,198 | 24e4557ad146bf4f105f4a4080b8c6a902527c47698cca0d6496811823ec2fe1 | Verification deliverable file |
| CHANGELOG.md | 4,789 | 1825b6b1960c774491787a42cb0e5631366226d12c6e8d7de033e31d0552a0cb | Engineering change log from Phase 1 to Phase 3 |
| COMPLETION_STATUS.md | 7,174 | 32009ddba966ea56a0e853df2fa410e34871ae2ce5976c53085da41718725434 | Task-by-task requirement completion matrix |
| conftest.py | 536 | 810ec386c39c9662ca620be4160446354cadc701ab50fd2a8c68c9c2af2ed79d | Pytest discovery and path configuration hook |
| EXECUTIVE_SUMMARY.md | 5,633 | c1dbd9e0028a06f62468ff78c3317cb89361bb0c434f43f3168bdd15e5a02f29 | High-level sign-off summary and priority scorecard |
| README.md | 7,747 | 68eb2f42acc5e2d773b84e8472a84ee6b5667bfb3b63fdfd8e3ed77b1285ad09 | Main package overview, directory map, and quickstart |
| REPRODUCE_ALL.md | 4,146 | 53710d39e9d0bf6b60ecc0d2d81245126560eeaaf7d248b05b11b41439546c11 | Independent step-by-step reproduction guide |
