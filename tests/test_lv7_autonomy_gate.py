from __future__ import annotations

import json
import subprocess
import sys

from aibenchie.lv7_autonomy_gate import run_gate, validate_lv7_autonomy_evidence
from tests.conftest import ROOT


def fact(signal_id: str) -> dict:
    return {
        "schema": "lv7.fact.v1",
        "id": f"{signal_id}:fact",
        "signal_id": signal_id,
        "kind": "test",
        "subject": signal_id,
        "predicate": "observed",
        "value": True,
        "confidence": 1.0,
    }


def trace(signal_type: str, *, intent_type: str = "sleep", approval_required: bool = False, risk: str = "passive") -> dict:
    signal_id = f"sig_{signal_type.replace('.', '_')}"
    proposed_actions = []
    if intent_type != "sleep":
        proposed_actions = [
            {
                "action": "test_action",
                "capability": "test.capability",
                "risk": risk,
                "approval_required": approval_required,
            }
        ]
    policy_decision = "ask" if approval_required or risk in {"medium", "high", "critical"} else "allow"
    action_state = "none" if intent_type == "sleep" else ("pending_approval" if policy_decision == "ask" else "queued_connector")
    return {
        "schema": "lv7.loop_trace.v1",
        "id": f"trace:{signal_id}",
        "started_at": "2026-05-11T12:00:00Z",
        "signal": {
            "schema": "lv7.signal.v1",
            "id": signal_id,
            "type": signal_type,
            "source": "test",
            "observed_at": "2026-05-11T12:00:00Z",
            "facts": {},
        },
        "facts": [fact(signal_id)],
        "state": {
            "schema": "lv7.agent_state.v1",
            "id": f"state:{signal_id}",
            "updated_at": "2026-05-11T12:00:00Z",
            "resources": {"pressure_level": "unknown"},
            "pending_facts": [fact(signal_id)],
        },
        "attention_decision": {
            "schema": "lv7.attention_decision.v1",
            "id": f"attention:{signal_id}",
            "score": 0.5,
            "selected": intent_type != "sleep",
            "reason": "test",
            "inputs": {},
        },
        "intent": {
            "schema": "lv7.intent.v1",
            "id": f"intent:{signal_id}",
            "type": intent_type,
            "category": "test",
            "priority": 0.5,
            "approval_required": approval_required,
            "risk": risk,
            "summary": "test intent",
            "proposed_actions": proposed_actions,
        },
        "policy_decision": {
            "schema": "lv7.policy_decision.v1",
            "id": f"policy:{signal_id}",
            "intent_id": f"intent:{signal_id}",
            "decision": policy_decision,
            "reason": "test",
        },
        "action_record": {
            "schema": "lv7.action_record.v1",
            "id": f"action:{signal_id}",
            "intent_id": f"intent:{signal_id}",
            "state": action_state,
            "capability": "none" if intent_type == "sleep" else "test.capability",
            "risk": risk,
            "approval_required": policy_decision == "ask",
        },
    }


def valid_evidence() -> dict:
    scenarios = [
        {"id": "resource", "signal_type": "resource.pressure", "ok": True, "failure": "", "trace": trace("resource.pressure")},
        {"id": "presence", "signal_type": "presence.changed", "ok": True, "failure": "", "trace": trace("presence.changed", intent_type="message")},
        {"id": "forgejo", "signal_type": "forgejo.pr_status", "ok": True, "failure": "", "trace": trace("forgejo.pr_status", intent_type="plan")},
    ]
    return {
        "schema": "lv7.autonomy_evidence.v1",
        "ok": True,
        "verdict": "pass",
        "summary": {
            "scenarios": 3,
            "pass": 3,
            "fail": 0,
            "by_signal_type": {
                "resource.pressure": {"pass": 1, "fail": 0},
                "presence.changed": {"pass": 1, "fail": 0},
                "forgejo.pr_status": {"pass": 1, "fail": 0},
            },
        },
        "scenarios": scenarios,
    }


def failures(verdict: dict) -> dict[str, str]:
    return {item["name"]: item["failure"] for item in verdict["checks"] if not item["ok"]}


def test_lv7_autonomy_gate_accepts_valid_evidence():
    verdict = validate_lv7_autonomy_evidence(valid_evidence())

    assert verdict["ok"] is True
    assert verdict["verdict"] == "pass"
    assert verdict["summary"]["fail"] == 0


def test_lv7_autonomy_gate_rejects_missing_required_signal_type():
    payload = valid_evidence()
    payload["scenarios"] = payload["scenarios"][:2]
    payload["summary"]["scenarios"] = 2
    payload["summary"]["pass"] = 2
    del payload["summary"]["by_signal_type"]["forgejo.pr_status"]

    verdict = validate_lv7_autonomy_evidence(payload)

    assert verdict["ok"] is False
    assert failures(verdict)["evidence.required_signal_types"] == "required_signal_type_missing"


def test_lv7_autonomy_gate_rejects_policy_bypass_for_approval_required_intent():
    payload = valid_evidence()
    bad_trace = trace("resource.pressure", intent_type="ask", approval_required=True, risk="medium")
    bad_trace["policy_decision"]["decision"] = "allow"
    bad_trace["action_record"]["state"] = "queued_connector"
    bad_trace["action_record"]["approval_required"] = False
    payload["scenarios"][0]["trace"] = bad_trace

    verdict = validate_lv7_autonomy_evidence(payload)

    assert verdict["ok"] is False
    found = failures(verdict)
    assert found["resource.approval.policy"] == "approval_required_intent_not_asked"
    assert found["resource.approval.action"] == "approval_required_action_not_pending"


def test_lv7_autonomy_gate_rejects_missing_trace_primitive():
    payload = valid_evidence()
    del payload["scenarios"][0]["trace"]["policy_decision"]

    verdict = validate_lv7_autonomy_evidence(payload)

    assert verdict["ok"] is False
    assert failures(verdict)["resource.trace.policy_decision"] == "primitive_missing"


def test_lv7_autonomy_gate_cli_returns_nonzero_for_invalid_evidence(tmp_path):
    payload = valid_evidence()
    payload["ok"] = False
    evidence_path = tmp_path / "lv7-autonomy.json"
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "aibenchie.lv7_autonomy_gate", str(evidence_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "fail" in completed.stdout


def test_lv7_autonomy_gate_cli_accepts_valid_evidence(tmp_path):
    evidence_path = tmp_path / "lv7-autonomy.json"
    evidence_path.write_text(json.dumps(valid_evidence()), encoding="utf-8")

    verdict = run_gate(evidence_path)

    assert verdict["ok"] is True
