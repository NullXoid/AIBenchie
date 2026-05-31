from __future__ import annotations

from pathlib import Path

from evals import router_backend, router_gate, router_hybrid_gate
from training import router_embedding_classifier


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ROUTE_CODES = {
    "R00": "chat.no_action",
    "R01": "answer.question",
    "R02": "ask_clarifying_question",
    "R03": "vision.describe_image",
    "R04": "vision.ocr_image",
    "R05": "vision.edit_image",
    "R06": "console.open_ui",
    "R07": "console.edit_file",
    "R08": "console.run_command",
    "R09": "agent.preview_plan",
    "R10": "agent.start_job",
    "R11": "web.lookup",
    "R12": "file.search",
    "R13": "memory.save_preference",
    "R14": "safety.refuse",
}
EXPECTED_STRICT_CONFIRM_ROUTES = {
    "agent.start_job",
    "console.run_command",
    "console.edit_file",
    "vision.edit_image",
    "memory.save_preference",
}
EXPECTED_SAFE_NON_ACTION_ROUTES = {
    "chat.no_action",
    "answer.question",
    "ask_clarifying_question",
    "agent.preview_plan",
    "safety.refuse",
}
EXPECTED_SAFE_STAGE_CODES = {"R00", "R01", "R02", "R09", "R14"}
EXPECTED_SAFE_READ_CODES = {"R03", "R04", "R06", "R11", "R12"}
EXPECTED_RISKY_CODES = {"R05", "R07", "R08", "R10", "R13"}
EXPECTED_ROUTE_CODE_TO_GATE = {
    **{code: "G00" for code in ("R00", "R09", "R14")},
    "R01": "G01",
    "R02": "G02",
    **{code: "G03" for code in EXPECTED_SAFE_READ_CODES},
    **{code: "G04" for code in EXPECTED_RISKY_CODES},
}


def test_aibenchie_router_evaluation_contract_has_all_parts():
    assert router_gate.ROUTE_CODES == EXPECTED_ROUTE_CODES
    assert router_embedding_classifier.ROUTE_CODES == EXPECTED_ROUTE_CODES
    assert router_gate.ROUTE_TO_CODE == {route: code for code, route in EXPECTED_ROUTE_CODES.items()}
    assert router_embedding_classifier.ROUTE_TO_CODE == router_gate.ROUTE_TO_CODE

    assert router_gate.STRICT_CONFIRM_ROUTES == EXPECTED_STRICT_CONFIRM_ROUTES
    assert router_gate.SAFE_NON_ACTION_ROUTES == EXPECTED_SAFE_NON_ACTION_ROUTES
    assert router_embedding_classifier.SAFE_STAGE_CODES == EXPECTED_SAFE_STAGE_CODES
    assert router_embedding_classifier.SAFE_READ_ROUTE_CODES == EXPECTED_SAFE_READ_CODES
    assert router_embedding_classifier.RISKY_ROUTE_CODES == EXPECTED_RISKY_CODES

    assert router_hybrid_gate.ROUTE_CODE_TO_GATE == EXPECTED_ROUTE_CODE_TO_GATE
    assert router_hybrid_gate.SAFE_STAGE_CODES == EXPECTED_SAFE_STAGE_CODES
    assert router_hybrid_gate.SAFE_READ_CODES == EXPECTED_SAFE_READ_CODES
    assert router_hybrid_gate.RISKY_CODES == EXPECTED_RISKY_CODES

    assert {"embedding_classifier", "encoder_stage0", "hf_transformers", "ollama"} <= router_backend.SUPPORTED_BACKENDS


def test_aibenchie_router_evaluation_code_does_not_emit_lv7_runtime_bridge_contract():
    router_sources = [
        *sorted((ROOT / "evals").glob("router*.py")),
        *sorted((ROOT / "training").glob("router*.py")),
    ]
    forbidden_runtime_terms = (
        "lv7.model_intent_response.v1",
        "lv7_autonomy.router_intent_bridge",
        "bridge_request(",
        "intent_from_router_route(",
        "ROUTE_INTENT_POLICY",
    )

    assert router_sources
    assert not (ROOT / "lv7_autonomy" / "router_intent_bridge.py").exists()

    for path in router_sources:
        source = path.read_text(encoding="utf-8")
        for term in forbidden_runtime_terms:
            assert term not in source, f"{path.relative_to(ROOT)} should not own Lv-7 runtime bridge behavior"
