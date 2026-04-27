from __future__ import annotations

import json

import aibenchie_local
from aibenchie.release_artifacts import emit_release_artifacts_manifest, verify_release_artifacts_manifest


def _package_files(tmp_path):
    wrapper = tmp_path / "packages" / "wrapper.zip"
    android = tmp_path / "packages" / "nullxoid-companion.apk"
    public = tmp_path / "packages" / "public-site.zip"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_bytes(b"wrapper package")
    android.write_bytes(b"android package")
    public.write_bytes(b"public package")
    return {"wrapper": wrapper, "android": android, "public": public}


def test_emit_release_artifacts_manifest_and_verify_hashes(tmp_path):
    output = tmp_path / "release-artifacts.json"
    payload = emit_release_artifacts_manifest(
        packages=_package_files(tmp_path),
        output=output,
        root=tmp_path,
        sidecar_dir=tmp_path / "attestation",
        signing_key_id="test-release-key",
    )

    result = verify_release_artifacts_manifest(output, root=tmp_path)

    assert payload["schema_version"] == 1
    assert payload["required_artifact_kinds"] == ["wrapper", "android", "public"]
    assert result.ok is True
    assert result.failures == []
    assert {artifact["kind"] for artifact in result.artifacts} == {"wrapper", "android", "public"}

    manifest = json.loads(output.read_text(encoding="utf-8"))
    for artifact in manifest["artifacts"]:
        assert artifact["digest"]["algorithm"] == "sha256"
        assert len(artifact["digest"]["value"]) == 64
        assert artifact["signature"]["key_id"] == "test-release-key"
        for section in ("sbom", "signature", "manifest"):
            sidecar = tmp_path / artifact[section]["path"]
            assert sidecar.exists()
            assert len(artifact[section]["sha256"]) == 64


def test_verify_release_artifacts_manifest_rejects_tampered_sidecar(tmp_path):
    output = tmp_path / "release-artifacts.json"
    emit_release_artifacts_manifest(
        packages=_package_files(tmp_path),
        output=output,
        root=tmp_path,
        sidecar_dir=tmp_path / "attestation",
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    sbom_path = tmp_path / payload["artifacts"][0]["sbom"]["path"]
    sbom_path.write_text("tampered\n", encoding="utf-8")

    result = verify_release_artifacts_manifest(output, root=tmp_path)

    assert result.ok is False
    assert any("sbom_sha256_mismatch" in failure for failure in result.failures)


def test_verify_release_artifacts_manifest_requires_wrapper_android_public(tmp_path):
    output = tmp_path / "release-artifacts.json"
    payload = {
        "schema_version": 1,
        "artifacts": [],
    }
    output.write_text(json.dumps(payload), encoding="utf-8")

    result = verify_release_artifacts_manifest(output, root=tmp_path)

    assert result.ok is False
    assert "required_artifact_missing:wrapper" in result.failures
    assert "required_artifact_missing:android" in result.failures
    assert "required_artifact_missing:public" in result.failures


def test_release_artifacts_cli_emit_and_verify(tmp_path, capsys):
    packages = _package_files(tmp_path)
    output = tmp_path / "release-artifacts.json"

    emit_exit = aibenchie_local.main(
        [
            "--emit-release-artifacts",
            "--wrapper-package",
            str(packages["wrapper"]),
            "--android-package",
            str(packages["android"]),
            "--public-package",
            str(packages["public"]),
            "--release-artifacts-output",
            str(output),
            "--release-artifacts-sidecar-dir",
            str(tmp_path / "attestation"),
            "--release-artifact-key-id",
            "test-release-key",
            "--json",
        ]
    )
    verify_exit = aibenchie_local.main(
        [
            "--verify-release-artifacts",
            "--release-artifacts",
            str(output),
            "--json",
        ]
    )
    captured = capsys.readouterr().out

    assert emit_exit == 0
    assert verify_exit == 0
    assert '"ok": true' in captured
