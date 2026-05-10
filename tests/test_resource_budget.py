from __future__ import annotations

import json

from aibenchie import resource_budget


def write_bytes(path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def test_resource_budget_passes_for_bounded_paths(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    logs = tmp_path / "logs"
    write_bytes(cache / "pip" / "wheel", 128)
    write_bytes(logs / "backend.log", 256)

    budgets = [
        {"name": "cache", "pattern": str(cache), "max_bytes": 1024},
        {"name": "logs", "pattern": str(logs), "max_bytes": 1024},
        {"name": "missing_optional", "pattern": str(tmp_path / "missing-*"), "max_bytes": 0},
    ]
    env = {
        "AIBENCHIE_RESOURCE_PROFILE": "test",
        "AIBENCHIE_RESOURCE_BUDGETS_JSON": json.dumps(budgets),
        "AIBENCHIE_RESOURCE_DISK_ROOT": str(tmp_path),
        "AIBENCHIE_RESOURCE_MIN_FREE_MB": "1",
        "AIBENCHIE_RESOURCE_MAX_USED_PERCENT": "99.9",
    }

    result = resource_budget.run_resource_budget_check(env)

    assert result.ok is True
    assert result.disk.ok is True
    assert [item.name for item in result.items] == ["cache", "logs", "missing_optional"]
    assert result.items[0].bytes_used == 128
    assert result.items[1].bytes_used == 256
    assert result.items[2].ok is True


def test_resource_budget_fails_when_cache_exceeds_limit(tmp_path):
    cache = tmp_path / "cache"
    write_bytes(cache / "large.tmp", 2048)
    budgets = [{"name": "cache", "pattern": str(cache), "max_bytes": 1024}]
    env = {
        "AIBENCHIE_RESOURCE_PROFILE": "test",
        "AIBENCHIE_RESOURCE_BUDGETS_JSON": json.dumps(budgets),
        "AIBENCHIE_RESOURCE_DISK_ROOT": str(tmp_path),
        "AIBENCHIE_RESOURCE_MIN_FREE_MB": "1",
        "AIBENCHIE_RESOURCE_MAX_USED_PERCENT": "99.9",
    }

    result = resource_budget.run_resource_budget_check(env)

    assert result.ok is False
    assert result.items[0].ok is False
    assert result.items[0].failure == "budget_exceeded"


def test_resource_budget_fails_when_required_path_is_missing(tmp_path):
    budgets = [{"name": "backend_venv", "pattern": str(tmp_path / ".venv"), "max_bytes": 1024, "required": True}]
    env = {
        "AIBENCHIE_RESOURCE_PROFILE": "test",
        "AIBENCHIE_RESOURCE_BUDGETS_JSON": json.dumps(budgets),
        "AIBENCHIE_RESOURCE_DISK_ROOT": str(tmp_path),
        "AIBENCHIE_RESOURCE_MIN_FREE_MB": "1",
        "AIBENCHIE_RESOURCE_MAX_USED_PERCENT": "99.9",
    }

    result = resource_budget.run_resource_budget_check(env)

    assert result.ok is False
    assert result.items[0].failure == "required_path_missing"


def test_ct400_default_profile_blocks_heavy_venv_backup(monkeypatch, tmp_path):
    backend = tmp_path / "home" / "deploy" / "NullXoid" / "NullXoid"
    write_bytes(backend / ".venv" / "pyvenv.cfg", 10)
    write_bytes(backend / ".venv-heavy-backup-1" / "torch.whl", 10)

    def fake_default_budgets():
        return [
            resource_budget.ResourceBudget("backend_venv", str(backend / ".venv"), 300 * resource_budget.MIB, True),
            resource_budget.ResourceBudget("heavy_venv_backups", str(backend / ".venv-heavy-backup-*"), 0),
        ]

    monkeypatch.setattr(resource_budget, "default_ct400_wrapper_budgets", fake_default_budgets)
    env = {
        "AIBENCHIE_RESOURCE_PROFILE": "ct400-wrapper",
        "AIBENCHIE_RESOURCE_DISK_ROOT": str(tmp_path),
        "AIBENCHIE_RESOURCE_MIN_FREE_MB": "1",
        "AIBENCHIE_RESOURCE_MAX_USED_PERCENT": "99.9",
    }

    result = resource_budget.run_resource_budget_check(env)

    assert result.ok is False
    failures = {item.name: item.failure for item in result.items if not item.ok}
    assert failures == {"heavy_venv_backups": "budget_exceeded"}


def valid_runtime_evidence() -> dict:
    return {
        "schema": "echolabs.resource-manager-runtime.v1",
        "template": False,
        "profiles": {
            "ct400-wrapper": {
                "max_parallel_jobs": 2,
                "max_lease_seconds": 900,
                "max_memory_mb": 4096,
                "retention_seconds": 86400,
            }
        },
        "leases": [
            {
                "id": "lease_test",
                "capability": "model.inference",
                "profile": "ct400-wrapper",
                "approved": True,
                "max_duration_seconds": 300,
                "max_memory_mb": 2048,
                "cleanup_after_seconds": 3600,
                "trace_id": "trace_test",
            }
        ],
        "enforcement": {
            "lease_required_for_heavy_work": True,
            "missing_lease_denied": True,
            "expired_lease_denied": True,
            "mismatched_lease_denied": True,
            "parallel_limit_denied": True,
        },
        "cleanup": {
            "enabled": True,
            "last_success_at": "2026-05-10T00:00:00Z",
            "deleted_expired_leases": 1,
            "audit_event_recorded": True,
        },
        "pressure": {
            "profile": "ct400-wrapper",
            "level": "normal",
            "sampled_at": "2026-05-10T00:00:00Z",
            "active_leases": 1,
            "queued_jobs": 0,
        },
    }


def test_resource_budget_can_require_runtime_evidence(tmp_path):
    proof = tmp_path / "resource-runtime.json"
    proof.write_text(json.dumps(valid_runtime_evidence()), encoding="utf-8")
    env = {
        "AIBENCHIE_RESOURCE_PROFILE": "test",
        "AIBENCHIE_RESOURCE_BUDGETS_JSON": "[]",
        "AIBENCHIE_RESOURCE_DISK_ROOT": str(tmp_path),
        "AIBENCHIE_RESOURCE_MIN_FREE_MB": "1",
        "AIBENCHIE_RESOURCE_MAX_USED_PERCENT": "99.9",
        "AIBENCHIE_RESOURCE_MANAGER_EVIDENCE": str(proof),
        "AIBENCHIE_RESOURCE_MANAGER_REQUIRE_RUNTIME": "1",
    }

    result = resource_budget.run_resource_budget_check(env)

    assert result.ok is True
    assert result.runtime["ok"] is True
    assert result.runtime["required"] is True


def test_resource_budget_requires_explicit_runtime_evidence_path(tmp_path):
    env = {
        "AIBENCHIE_RESOURCE_PROFILE": "test",
        "AIBENCHIE_RESOURCE_BUDGETS_JSON": "[]",
        "AIBENCHIE_RESOURCE_DISK_ROOT": str(tmp_path),
        "AIBENCHIE_RESOURCE_MIN_FREE_MB": "1",
        "AIBENCHIE_RESOURCE_MAX_USED_PERCENT": "99.9",
        "AIBENCHIE_RESOURCE_MANAGER_REQUIRE_RUNTIME": "1",
    }

    result = resource_budget.run_resource_budget_check(env)

    assert result.ok is False
    failures = {check["name"]: check["failure"] for check in result.runtime["checks"] if not check["ok"]}
    assert failures["runtime.evidence_file"] == "missing_runtime_evidence_path"


def test_resource_runtime_evidence_rejects_unbounded_leases(tmp_path):
    payload = valid_runtime_evidence()
    payload["leases"][0]["max_duration_seconds"] = 5000
    payload["pressure"]["level"] = "critical"
    proof = tmp_path / "resource-runtime.json"
    proof.write_text(json.dumps(payload), encoding="utf-8")
    env = {
        "AIBENCHIE_RESOURCE_PROFILE": "test",
        "AIBENCHIE_RESOURCE_BUDGETS_JSON": "[]",
        "AIBENCHIE_RESOURCE_DISK_ROOT": str(tmp_path),
        "AIBENCHIE_RESOURCE_MIN_FREE_MB": "1",
        "AIBENCHIE_RESOURCE_MAX_USED_PERCENT": "99.9",
        "AIBENCHIE_RESOURCE_MANAGER_EVIDENCE": str(proof),
        "AIBENCHIE_RESOURCE_MANAGER_REQUIRE_RUNTIME": "1",
    }

    result = resource_budget.run_resource_budget_check(env)

    assert result.ok is False
    failures = {check["name"]: check["failure"] for check in result.runtime["checks"] if not check["ok"]}
    assert failures["runtime.leases[0].duration"] == "lease_duration_unbounded"
    assert failures["runtime.pressure.level"] == "pressure_not_safe"


def test_resource_runtime_evidence_reports_malformed_numbers(tmp_path):
    payload = valid_runtime_evidence()
    payload["leases"][0]["max_memory_mb"] = "large"
    payload["cleanup"]["deleted_expired_leases"] = "many"
    proof = tmp_path / "resource-runtime.json"
    proof.write_text(json.dumps(payload), encoding="utf-8")
    env = {
        "AIBENCHIE_RESOURCE_PROFILE": "test",
        "AIBENCHIE_RESOURCE_BUDGETS_JSON": "[]",
        "AIBENCHIE_RESOURCE_DISK_ROOT": str(tmp_path),
        "AIBENCHIE_RESOURCE_MIN_FREE_MB": "1",
        "AIBENCHIE_RESOURCE_MAX_USED_PERCENT": "99.9",
        "AIBENCHIE_RESOURCE_MANAGER_EVIDENCE": str(proof),
        "AIBENCHIE_RESOURCE_MANAGER_REQUIRE_RUNTIME": "1",
    }

    result = resource_budget.run_resource_budget_check(env)

    assert result.ok is False
    failures = {check["name"]: check["failure"] for check in result.runtime["checks"] if not check["ok"]}
    assert failures["runtime.leases[0].memory"] == "lease_memory_unbounded"
    assert failures["runtime.cleanup.deleted_expired_leases"] == "cleanup_deleted_count_invalid"


def test_resource_runtime_evidence_requires_enforcement_denials(tmp_path):
    payload = valid_runtime_evidence()
    del payload["enforcement"]["missing_lease_denied"]
    payload["enforcement"]["parallel_limit_denied"] = False
    proof = tmp_path / "resource-runtime.json"
    proof.write_text(json.dumps(payload), encoding="utf-8")
    env = {
        "AIBENCHIE_RESOURCE_PROFILE": "test",
        "AIBENCHIE_RESOURCE_BUDGETS_JSON": "[]",
        "AIBENCHIE_RESOURCE_DISK_ROOT": str(tmp_path),
        "AIBENCHIE_RESOURCE_MIN_FREE_MB": "1",
        "AIBENCHIE_RESOURCE_MAX_USED_PERCENT": "99.9",
        "AIBENCHIE_RESOURCE_MANAGER_EVIDENCE": str(proof),
        "AIBENCHIE_RESOURCE_MANAGER_REQUIRE_RUNTIME": "1",
    }

    result = resource_budget.run_resource_budget_check(env)

    assert result.ok is False
    failures = {check["name"]: check["failure"] for check in result.runtime["checks"] if not check["ok"]}
    assert failures["runtime.enforcement.missing_lease_denied"] == "missing_lease_not_denied"
    assert failures["runtime.enforcement.parallel_limit_denied"] == "parallel_limit_not_denied"


def test_resource_runtime_evidence_rejects_duplicate_or_unknown_leases(tmp_path):
    payload = valid_runtime_evidence()
    payload["leases"].append(
        {
            "id": "lease_test",
            "capability": "",
            "profile": "unknown",
            "approved": True,
            "max_duration_seconds": 300,
            "max_memory_mb": 2048,
            "cleanup_after_seconds": 3600,
            "trace_id": "",
        }
    )
    proof = tmp_path / "resource-runtime.json"
    proof.write_text(json.dumps(payload), encoding="utf-8")
    env = {
        "AIBENCHIE_RESOURCE_PROFILE": "test",
        "AIBENCHIE_RESOURCE_BUDGETS_JSON": "[]",
        "AIBENCHIE_RESOURCE_DISK_ROOT": str(tmp_path),
        "AIBENCHIE_RESOURCE_MIN_FREE_MB": "1",
        "AIBENCHIE_RESOURCE_MAX_USED_PERCENT": "99.9",
        "AIBENCHIE_RESOURCE_MANAGER_EVIDENCE": str(proof),
        "AIBENCHIE_RESOURCE_MANAGER_REQUIRE_RUNTIME": "1",
    }

    result = resource_budget.run_resource_budget_check(env)

    assert result.ok is False
    failures = {check["name"]: check["failure"] for check in result.runtime["checks"] if not check["ok"]}
    assert failures["runtime.leases[1].id_unique"] == "lease_id_duplicate"
    assert failures["runtime.leases[1].capability"] == "lease_capability_missing"
    assert failures["runtime.leases[1].profile"] == "lease_profile_unknown"
    assert failures["runtime.leases[1].trace_id"] == "lease_trace_id_missing"


def test_resource_runtime_evidence_requires_cleanup_audit_and_pressure_sample(tmp_path):
    payload = valid_runtime_evidence()
    payload["cleanup"]["audit_event_recorded"] = False
    payload["pressure"]["sampled_at"] = ""
    payload["pressure"]["queued_jobs"] = 10
    proof = tmp_path / "resource-runtime.json"
    proof.write_text(json.dumps(payload), encoding="utf-8")
    env = {
        "AIBENCHIE_RESOURCE_PROFILE": "test",
        "AIBENCHIE_RESOURCE_BUDGETS_JSON": "[]",
        "AIBENCHIE_RESOURCE_DISK_ROOT": str(tmp_path),
        "AIBENCHIE_RESOURCE_MIN_FREE_MB": "1",
        "AIBENCHIE_RESOURCE_MAX_USED_PERCENT": "99.9",
        "AIBENCHIE_RESOURCE_MANAGER_EVIDENCE": str(proof),
        "AIBENCHIE_RESOURCE_MANAGER_REQUIRE_RUNTIME": "1",
    }

    result = resource_budget.run_resource_budget_check(env)

    assert result.ok is False
    failures = {check["name"]: check["failure"] for check in result.runtime["checks"] if not check["ok"]}
    assert failures["runtime.cleanup.audit_event_recorded"] == "cleanup_audit_missing"
    assert failures["runtime.pressure.sampled_at"] == "pressure_sample_missing"
    assert failures["runtime.pressure.queued_jobs"] == "queued_jobs_above_profile"
