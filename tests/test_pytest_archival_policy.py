from __future__ import annotations

from tests import conftest


def test_known_artifact_dependent_tests_are_archival_by_default():
    assert conftest.RUN_ARCHIVAL_ENV == "AIBENCHIE_RUN_ARCHIVAL_TESTS"
    assert conftest._is_archival_test_file("tests/test_analyze_v1_4_1_external_m6_runtime_eval.py")
    assert conftest._is_archival_test_file("tests/test_dpo_smoke_v1_2_4.py")


def test_current_release_and_suite_gates_remain_default_tests():
    assert not conftest._is_archival_test_file("tests/test_release_report.py")
    assert not conftest._is_archival_test_file("tests/test_suite_security.py")
    assert not conftest._is_archival_test_file("tests/test_analyze_v1_5_13_cancel_timeout_fallback_android_contract.py")
