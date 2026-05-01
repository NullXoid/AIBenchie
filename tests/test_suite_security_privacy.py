from __future__ import annotations

import json

import aibenchie_local
from aibenchie import suite_security_privacy


def _m35_pass():
    return {
        "ok": True,
        "m35PlatformAdapters": {
            "website": "passed",
            "wrapper": "passed",
            "windows": "passed",
            "android": "passed",
            "unsupportedRouteDenial": "passed",
            "credentialLeakCheck": "passed",
        },
    }


def test_m36_gate_outputs_pass_with_accepted_pending(monkeypatch, tmp_path):
    monkeypatch.setattr(suite_security_privacy, "run_nullbridge_platform_adapters_from_env", _m35_pass)

    result = suite_security_privacy.run_suite_security_privacy_check(
        env={
            "AIBENCHIE_M36_ROOT": str(tmp_path),
        }
    )
    payload = result.as_dict()

    assert payload["ok"] is True
    assert payload["releaseVerdict"] == "pass_with_accepted_pending"
    assert payload["blockingFailures"] == []
    assert set(payload["m36SecurityPrivacy"]) == set(suite_security_privacy.GATE_NAMES)
    assert payload["m36SecurityPrivacy"]["credentialIsolation"]["status"] == "passed"
    assert payload["knownPending"]["m37WebsiteAuthCleanup"] == [
        "localStorage audit-token cleanup",
        "legacy token-header fallback inventory",
        "SSE query-token cleanup",
    ]


def test_route_privacy_inventory_fails_missing_registered_route(tmp_path):
    nullbridge = tmp_path / "NullBridge"
    policy = nullbridge / "backend" / "infra" / "nullbridge" / "route-policy.json"
    policy.parent.mkdir(parents=True)
    policy.write_text(
        json.dumps(
            {
                "version": 1,
                "rules": [
                    {
                        "caller": "new_backend",
                        "targetRoles": ["diagnostics"],
                        "capabilities": ["suite.demo.echo"],
                        "allow": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    inventory = {
        "version": 1,
        "routes": [
            {
                "routeId": "aibenchie.cli.suite-security-privacy",
                "platform": "aibenchie",
                "authRequirement": "local operator",
                "sensitiveDataClass": "verdict",
                "storageBehavior": "public safe",
                "logBehavior": "redacted",
                "frontendExposure": "none",
                "expectedPrivacyGate": "M36",
                "evidence": ["fixture"],
                "status": "covered",
            }
        ],
        "exemptions": [],
    }

    failures, summary = suite_security_privacy.validate_route_inventory(
        inventory,
        tmp_path,
        {"AIBENCHIE_NULLBRIDGE_REPO": str(nullbridge)},
    )

    assert "ROUTE_PRIVACY_INVENTORY_MISSING:nullbridge.route_policy.new_backend" in failures
    assert summary["missingRoutes"] == ["nullbridge.route_policy.new_backend"]


def test_accepted_pending_does_not_bypass_canary_leak(monkeypatch, tmp_path):
    monkeypatch.setattr(suite_security_privacy, "run_nullbridge_platform_adapters_from_env", _m35_pass)
    public = tmp_path / "public_export" / "summary.json"
    public.parent.mkdir(parents=True)
    public.write_text(
        json.dumps({"leak": suite_security_privacy.CANARIES["private_report_key"]}),
        encoding="utf-8",
    )

    result = suite_security_privacy.run_suite_security_privacy_check(
        env={
            "AIBENCHIE_M36_ROOT": str(tmp_path),
        }
    )
    payload = result.as_dict()

    assert payload["ok"] is False
    assert payload["releaseVerdict"] == "blocks_release"
    assert any("ARTIFACT_SANDBOX_LEAK" in failure for failure in payload["blockingFailures"])
    assert payload["knownPending"]["m37WebsiteAuthCleanup"]


def test_prompt_editor_gate_redacts_fake_canaries():
    result = suite_security_privacy.gate_prompt_editor_leakage({})

    assert result.ok is True
    assert result.failures == []


def test_private_aibenchie_report_gate_checks_encrypted_storage_and_public_summary():
    result = suite_security_privacy.gate_private_aibenchie_reports()

    assert result.ok is True
    assert "private report encrypted envelope check" in result.evidence
    assert "public summary sanitization check" in result.evidence


def test_ccc_scope_fixture_blocks_cross_scope_canary():
    result = suite_security_privacy.gate_ccc_scoping({})

    assert result.ok is True
    assert result.failures == []


def test_suite_security_privacy_cli_outputs_json(monkeypatch, capsys):
    class FakeResult:
        ok = True

        def as_dict(self):
            return {
                "ok": True,
                "releaseVerdict": "pass_with_accepted_pending",
                "blockingFailures": [],
                "m36SecurityPrivacy": {
                    "promptEditorLeakage": {"status": "passed", "severity": "blocking", "evidence": []}
                },
                "knownPending": {"m37WebsiteAuthCleanup": ["legacy token-header fallback inventory"]},
                "routeInventory": {"inventoryRoutes": 1},
            }

    monkeypatch.setattr(aibenchie_local, "run_suite_security_privacy_from_env", lambda: FakeResult())

    code = aibenchie_local.main(["--suite-security-privacy", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["releaseVerdict"] == "pass_with_accepted_pending"
