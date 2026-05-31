from __future__ import annotations

import yaml

from training import router_model_candidates as candidates


def test_candidate_order_separates_product_and_private_paths():
    production = candidates.ordered_candidates(candidates.PRODUCTION_PATH)
    private = candidates.ordered_candidates(candidates.PRIVATE_EXPERIMENTAL_PATH)

    assert [candidate.id for candidate in production] == [
        "embedding_classifier_router",
        "llama_3_2_3b_instruct",
        "lfm2_5_1_2b_instruct",
        "granite_4_0_micro",
    ]
    assert [candidate.id for candidate in private] == [
        "hammer2_1_1_5b",
        "xlam_2_1b_fc_r",
        "xlam_2_3b_fc_r",
    ]


def test_candidate_license_metadata_blocks_license_limited_promotion():
    hammer = candidates.candidate_by_id("hammer2_1_1_5b").with_serving_parity(candidates.SERVING_PROVEN)
    blockers = hammer.shadow_mode_blockers(focused_gates_passed=True, holdout_v3_passed=True)

    assert hammer.license_class == candidates.LICENSE_PRIVATE_EXPERIMENTAL
    assert "candidate_path_private_experimental" in blockers
    assert "license_not_production_reviewed" in blockers
    assert not hammer.shadow_mode_eligible(focused_gates_passed=True, holdout_v3_passed=True)


def test_embedding_classifier_is_co_primary_but_still_needs_gates_and_parity():
    embedding = candidates.candidate_by_id("embedding_classifier_router")

    assert embedding.training_kind == candidates.TRAINING_EMBEDDING_CLASSIFIER
    assert embedding.intended_backend == "embedding_classifier"
    assert embedding.shadow_mode_blockers(focused_gates_passed=False, holdout_v3_passed=False) == [
        "serving_parity_not_proven",
        "focused_gates_not_passed",
        "holdout_v3_not_passed",
    ]


def test_granite_is_diagnostic_only_after_failed_safety_gate():
    granite = candidates.candidate_by_id("granite_4_0_micro")

    assert granite.license_class == candidates.LICENSE_PRODUCTION_REVIEWED
    assert granite.recovery_status == candidates.RECOVERY_DIAGNOSTIC_ONLY
    blockers = granite.with_serving_parity(candidates.SERVING_PROVEN).shadow_mode_blockers(
        focused_gates_passed=True,
        holdout_v3_passed=True,
    )
    assert "candidate_not_active_for_promotion" in blockers
    assert not granite.with_serving_parity(candidates.SERVING_PROVEN).shadow_mode_eligible(
        focused_gates_passed=True,
        holdout_v3_passed=True,
    )


def test_custom_license_candidates_are_not_production_promotable_without_review():
    llama = candidates.candidate_by_id("llama_3_2_3b_instruct").with_serving_parity(candidates.SERVING_PROVEN)
    lfm = candidates.candidate_by_id("lfm2_5_1_2b_instruct").with_serving_parity(candidates.SERVING_PROVEN)

    assert "license_not_production_reviewed" in llama.shadow_mode_blockers(
        focused_gates_passed=True,
        holdout_v3_passed=True,
    )
    assert "license_not_production_reviewed" in lfm.shadow_mode_blockers(
        focused_gates_passed=True,
        holdout_v3_passed=True,
    )


def test_candidate_training_config_uses_route_code_recovery_contract():
    config = candidates.candidate_training_config("granite_4_0_micro")

    assert config["base_model"] == "ibm-granite/granite-4.0-micro"
    assert config["dataset"] == candidates.DIRECT_ACTION_DATASET
    assert config["eval_prompt_mode"] == "route_code"
    assert config["router_protocol"]["generation"] == candidates.ROUTE_CODE_GENERATION
    assert config["router_protocol"]["promotion_rules"]["shadow_mode_before_control"] is True
    assert config["router_protocol"]["promotion_rules"]["false_direct_actions_total"] == 0


def test_embedding_classifier_does_not_generate_qlora_config():
    try:
        candidates.candidate_training_config("embedding_classifier_router")
    except ValueError as exc:
        assert "does not use the QLoRA SFT training config path" in str(exc)
    else:
        raise AssertionError("embedding classifier should not produce a QLoRA config")


def test_wrapper_drift_is_always_scored_as_protocol_failure_for_tool_models():
    for candidate_id in ("lfm2_5_1_2b_instruct", "hammer2_1_1_5b", "xlam_2_1b_fc_r"):
        config = candidates.candidate_training_config(candidate_id)

        assert config["router_protocol"]["wrapper_drift_policy"] == "strict_protocol_failure"


def test_write_candidate_training_configs(tmp_path):
    paths = candidates.write_all_candidate_training_configs(tmp_path)

    assert len(paths) == 6
    assert not (tmp_path / "qlora_router_model_recovery_embedding_classifier_router.yaml").exists()
    written = yaml.safe_load((tmp_path / "qlora_router_model_recovery_granite_4_0_micro.yaml").read_text())
    assert written["candidate"]["id"] == "granite_4_0_micro"
    assert written["candidate"]["intended_backend"] == "hf_peft"
    assert written["router_protocol"]["generation"]["stop"] == ["\n", " ", "="]
