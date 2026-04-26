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
