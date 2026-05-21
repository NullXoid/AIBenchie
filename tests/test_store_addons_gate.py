from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aibenchie import release


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _proof(build_id: str, proof_type: str, *, extra: dict | None = None) -> dict:
    payload = {
        "schema_version": release.SCHEMA_VERSION,
        "build_id": build_id,
        "component": "Store/Add-ons",
        "proof_type": proof_type,
        "status": "pass",
        "generated_at": "2026-05-20T12:00:00Z",
        "source_commit": "abc123",
        "public_safe": True,
        "raw_evidence_local_only": True,
        "aibenchie_verdict": "pass",
        "blocked_reason": None,
    }
    if extra:
        payload.update(extra)
    return payload


def _valid_store_evidence(evidence_root: Path, build_id: str, *, expires_at: str = "2099-05-20T12:10:00Z") -> Path:
    proof_root = evidence_root / build_id / "store-proof"
    extras = {
        "capability-profile": {
            "profiles_match_store_config": True,
            "blocked_later_not_installable": True,
        },
        "install": {
            "install_succeeds": True,
            "installed_state_visible": True,
            "download_action_visible": True,
        },
        "uninstall": {
            "uninstall_succeeds": True,
            "uninstalled_state_visible": True,
            "feature_owned_data_only": True,
        },
        "enabled-disabled": {
            "enabled_state_visible": True,
            "disabled_state_visible": True,
            "state_consistency": True,
        },
        "unavailable-blocked": {
            "gated_not_installable": True,
            "blocked_not_installable": True,
            "experimental_not_normal_installable": True,
        },
        "release-stage-mapping": {
            "store_mapping_valid": True,
            "workflow_matrix_aligned": True,
            "blocked_later_not_installable": True,
        },
        "android-store": {
            "device_order": ["S23 FE", "A17"],
            "device_proof": {"S23 FE": "pass", "A17": "pass"},
            "states": sorted(release.STORE_ADDONS_REQUIRED_ANDROID_STATES),
            "messages_public_safe": True,
        },
        "public-safe-export": {
            "private_markers_rejected": True,
        },
        "optional-addons": {
            "nextcloud": {
                "required": False,
                "core_required": False,
                "status": "skipped_optional",
                "credentials_exposed": False,
                "private_server_exposed": False,
            },
        },
    }
    for filename, proof_type in release.STORE_ADDONS_REQUIRED_PROOFS.items():
        _write_json(proof_root / filename, _proof(build_id, proof_type, extra=extras[proof_type]))
    _write_json(
        proof_root / "store-addons-verdict.json",
        {
            "schema_version": release.SCHEMA_VERSION,
            "build_id": build_id,
            "component": "Store/Add-ons",
            "verdict": "pass",
            "generated_at": "2026-05-20T12:00:00Z",
            "expires_at": expires_at,
            "blocked_reason": None,
        },
    )
    (proof_root / "notes.md").write_text("MS6 Store/Add-ons gate passed.\n", encoding="utf-8")
    return proof_root


def test_store_addons_validator_accepts_valid_evidence(tmp_path):
    build_id = "ms6-store-test"
    _valid_store_evidence(tmp_path, build_id)

    result = release.validate_store_addons(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is True
    assert result["schema"] == release.STORE_ADDONS_VERDICT_SCHEMA
    assert result["verdict"] == "pass"
    assert result["install"] == "pass"
    assert result["optional_addons"] == "pass"


def test_store_addons_validator_blocks_missing_install_proof(tmp_path):
    build_id = "ms6-store-missing-install"
    proof_root = _valid_store_evidence(tmp_path, build_id)
    (proof_root / "install-proof.json").unlink()

    result = release.validate_store_addons(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert "install-proof.json:missing" in result["failures"]


def test_store_addons_validator_blocks_wrong_device_order(tmp_path):
    build_id = "ms6-store-device-order"
    proof_root = _valid_store_evidence(tmp_path, build_id)
    proof_path = proof_root / "android-store-proof.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["device_order"] = ["A17", "S23 FE"]
    _write_json(proof_path, proof)

    result = release.validate_store_addons(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert "android-store-proof.json:device_order:not_s23fe_then_a17" in result["failures"]


def test_store_addons_validator_blocks_nextcloud_core_required(tmp_path):
    build_id = "ms6-store-nextcloud-required"
    proof_root = _valid_store_evidence(tmp_path, build_id)
    proof_path = proof_root / "optional-addons-proof.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["nextcloud"]["core_required"] = True
    _write_json(proof_path, proof)

    result = release.validate_store_addons(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert "optional-addons-proof.json:nextcloud:required_by_default" in result["failures"]


def test_store_addons_validator_blocks_private_markers(tmp_path):
    build_id = "ms6-store-private"
    proof_root = _valid_store_evidence(tmp_path, build_id)
    proof_path = proof_root / "public-safe-export-proof.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["unsafe"] = "C:" + "\\Users" + "\\Example\\store.txt"
    _write_json(proof_path, proof)

    result = release.validate_store_addons(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert any(failure.endswith(":public_safety_marker") for failure in result["failures"])


def test_store_addons_validator_blocks_non_pass_proof(tmp_path):
    build_id = "ms6-store-non-pass"
    proof_root = _valid_store_evidence(tmp_path, build_id)
    proof_path = proof_root / "uninstall-proof.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["aibenchie_verdict"] = "manual-review"
    _write_json(proof_path, proof)

    result = release.validate_store_addons(
        evidence_root=tmp_path,
        build_id=build_id,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert "uninstall-proof.json:aibenchie_verdict:not_pass" in result["failures"]


def test_store_addons_validator_blocks_bad_store_mapping(tmp_path):
    build_id = "ms6-store-bad-config"
    _valid_store_evidence(tmp_path, build_id)
    store_config = release._load_store_capabilities(release.DEFAULT_STORE_CAPABILITIES)
    for item in store_config["capabilities"]:
        if item["workflow_id"] == "masked-edit":
            item["state"] = "installable"
            break
    config_path = tmp_path / "bad-store-capabilities.json"
    _write_json(config_path, store_config)

    result = release.validate_store_addons(
        evidence_root=tmp_path,
        build_id=build_id,
        store_capabilities=config_path,
        now=datetime(2026, 5, 20, 12, 1, tzinfo=timezone.utc),
    )

    assert result["ok"] is False
    assert "store-config:masked-edit:blocked_or_later_installable" in result["failures"]


def test_release_module_cli_validates_store_addons(tmp_path, capsys):
    build_id = "ms6-store-cli"
    _valid_store_evidence(tmp_path, build_id)

    code = release.main(
        [
            "validate-store-addons",
            "--evidence-root",
            str(tmp_path),
            "--build-id",
            build_id,
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["aibenchie_verdict"] == "pass"
