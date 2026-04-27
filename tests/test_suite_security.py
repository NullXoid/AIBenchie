from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import aibenchie_local
from aibenchie import suite_security
from aibenchie.generated_output_policy import GeneratedOutputPolicyResult


def _hosted_stack(ok: bool = True):
    routes = [
        SimpleNamespace(name="wrapper_page", ok=ok, failure="" if ok else "wrapper_fallback_page"),
        SimpleNamespace(name="backend_health", ok=True, failure=""),
    ]
    return SimpleNamespace(
        ok=ok,
        routes=routes,
        as_dict=lambda: {"ok": ok, "routes": [route.__dict__ for route in routes]},
    )


def _generated_policy(ok: bool = True):
    return GeneratedOutputPolicyResult(
        ok=ok,
        root="repo",
        budgets=[],
        forbidden_files=[],
        dirty_tracked_files=[],
        ignored_local_dirs=[],
    )


def test_secret_scan_rejects_private_key_without_emitting_secret(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "Bad file\n" + "-----BEGIN " + "OPENSSH PRIVATE KEY-----\nnot-a-real-key\n",
        encoding="utf-8",
    )

    result = suite_security.scan_public_files_for_secrets(tmp_path)
    payload = result.as_dict()

    assert result.ok is False
    assert payload["findings"] == [{"path": "README.md", "line": 2, "kind": "private_key"}]
    assert "not-a-real-key" not in json.dumps(payload)


def test_secret_scan_allows_runtime_placeholders(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        'AIBENCHIE_NULLXOID_PASSWORD="<runtime password>"\n'
        "NULLBRIDGE_SERVICE_TOKEN=[REDACTED_SERVICE_TOKEN]\n",
        encoding="utf-8",
    )

    result = suite_security.scan_public_files_for_secrets(tmp_path)

    assert result.ok is True
    assert result.findings == []


def test_suite_security_aggregates_required_checks(monkeypatch, tmp_path):
    monkeypatch.setattr(suite_security, "run_hosted_nullxoid_stack_check", lambda **kwargs: _hosted_stack(True))
    monkeypatch.setattr(
        suite_security,
        "scan_public_files_for_secrets",
        lambda root: suite_security.SecretScanResult(ok=True, root=str(root), scanned_files=1),
    )
    monkeypatch.setattr(suite_security, "run_generated_output_policy_check", lambda env: _generated_policy(True))

    result = suite_security.run_suite_security_check(env={"AIBENCHIE_SUITE_SECURITY_ROOT": str(tmp_path)})

    assert result.ok is True
    statuses = {check.name: check.status for check in result.checks}
    assert statuses["hosted_nullxoid_stack"] == "pass"
    assert statuses["public_secret_exposure"] == "pass"
    assert statuses["generated_output_policy"] == "pass"
    assert statuses["ephemeral_hosted_chat"] == "skip"
    assert statuses["local_nullbridge_trust_path"] == "skip"


def test_suite_security_fails_on_hosted_stack_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(suite_security, "run_hosted_nullxoid_stack_check", lambda **kwargs: _hosted_stack(False))
    monkeypatch.setattr(
        suite_security,
        "scan_public_files_for_secrets",
        lambda root: suite_security.SecretScanResult(ok=True, root=str(root), scanned_files=1),
    )
    monkeypatch.setattr(suite_security, "run_generated_output_policy_check", lambda env: _generated_policy(True))

    result = suite_security.run_suite_security_check(env={"AIBENCHIE_SUITE_SECURITY_ROOT": str(tmp_path)})

    assert result.ok is False
    hosted = next(check for check in result.checks if check.name == "hosted_nullxoid_stack")
    assert hosted.failure == "wrapper_fallback_page"


def test_suite_security_runs_ephemeral_chat_when_enabled(monkeypatch, tmp_path):
    called = {}

    def fake_ephemeral(**kwargs):
        called.update(kwargs)
        return SimpleNamespace(ok=True, failure="", as_dict=lambda: {"ok": True, "password": "[omitted]"})

    monkeypatch.setattr(suite_security, "run_hosted_nullxoid_stack_check", lambda **kwargs: _hosted_stack(True))
    monkeypatch.setattr(
        suite_security,
        "scan_public_files_for_secrets",
        lambda root: suite_security.SecretScanResult(ok=True, root=str(root), scanned_files=1),
    )
    monkeypatch.setattr(suite_security, "run_generated_output_policy_check", lambda env: _generated_policy(True))
    monkeypatch.setattr(suite_security, "run_ephemeral_hosted_nullxoid_chat_check", fake_ephemeral)

    result = suite_security.run_suite_security_check(
        env={
            "AIBENCHIE_SUITE_SECURITY_ROOT": str(tmp_path),
            "AIBENCHIE_SUITE_SECURITY_EPHEMERAL": "1",
            "AIBENCHIE_NULLXOID_EPHEMERAL_HELPER_ORIGIN": "http://127.0.0.1:8090",
        }
    )

    assert result.ok is True
    assert called["helper_origin"] == "http://127.0.0.1:8090"
    assert next(check for check in result.checks if check.name == "ephemeral_hosted_chat").status == "pass"


def test_suite_security_cli_prints_json_without_secret_values(monkeypatch, capsys):
    result = suite_security.SuiteSecurityResult(
        ok=True,
        origin="https://api.example.test",
        base_path="/nullxoid",
        checks=[
            suite_security.SuiteSecurityCheck(
                name="public_secret_exposure",
                ok=True,
                status="pass",
                severity="critical",
                detail={"findings": []},
            )
        ],
    )
    monkeypatch.setattr(aibenchie_local, "run_suite_security_check", lambda: result)

    exit_code = aibenchie_local.main(["--suite-security", "--json"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "api.example.test" in output
    assert "password" not in output.lower()


def test_suite_security_cli_returns_failure(monkeypatch, capsys):
    result = suite_security.SuiteSecurityResult(
        ok=False,
        origin="https://api.example.test",
        base_path="/nullxoid",
        checks=[
            suite_security.SuiteSecurityCheck(
                name="hosted_nullxoid_stack",
                ok=False,
                status="fail",
                severity="critical",
                failure="root_health_not_backend_json",
            )
        ],
    )
    monkeypatch.setattr(aibenchie_local, "run_suite_security_check", lambda: result)

    exit_code = aibenchie_local.main(["--suite-security"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "root_health_not_backend_json" in output
