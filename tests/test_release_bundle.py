from __future__ import annotations

import json
import zipfile

import aibenchie_local
from aibenchie.release_artifacts import verify_release_artifacts_manifest
from aibenchie.release_bundle import package_release_artifacts


TEST_SIGNING_SECRET = "test-release-bundle-secret"


def _write_build_sources(tmp_path):
    wrapper = tmp_path / "wrapper-dist"
    public = tmp_path / "public-dist"
    android = tmp_path / "android" / "app-release.apk"

    (wrapper / "assets").mkdir(parents=True)
    (wrapper / "node_modules" / "ignored").mkdir(parents=True)
    (public / "assets").mkdir(parents=True)
    android.parent.mkdir(parents=True)

    (wrapper / "index.html").write_text("<main>Wrapper</main>\n", encoding="utf-8")
    (wrapper / "assets" / "app.js").write_text("console.log('wrapper')\n", encoding="utf-8")
    (wrapper / "node_modules" / "ignored" / "junk.js").write_text("ignore me\n", encoding="utf-8")
    (public / "index.html").write_text("<main>Public site</main>\n", encoding="utf-8")
    (public / "assets" / "site.css").write_text("body { color: #fff; }\n", encoding="utf-8")
    (public / "content" / "verdicts").mkdir(parents=True)
    (public / "content" / "verdicts" / "aibenchie-release-artifact-freeze-summary.json").write_text(
        '{"schema":"aibenchie.release-artifact-freeze-summary.v1"}\n',
        encoding="utf-8",
    )
    android.write_bytes(b"fake apk bytes")
    return wrapper, android, public


def test_package_release_artifacts_emits_attestable_bundle(tmp_path, monkeypatch):
    wrapper, android, public = _write_build_sources(tmp_path)
    output_dir = tmp_path / "release-packages"
    manifest_output = output_dir / "release-artifacts.json"
    monkeypatch.setenv("AIBENCHIE_RELEASE_ATTESTATION_SECRET", TEST_SIGNING_SECRET)

    result = package_release_artifacts(
        wrapper_source=wrapper,
        android_source=android,
        public_source=public,
        output_dir=output_dir,
        manifest_output=manifest_output,
        signing_key_id="bundle-test-key",
    )
    verification = verify_release_artifacts_manifest(
        manifest_output,
        root=manifest_output.parent,
        signing_secret=TEST_SIGNING_SECRET,
    )

    assert result["ok"] is True
    assert verification.ok is True
    assert (output_dir / "nullxoid-wrapper.zip").exists()
    assert (output_dir / "nullxoid-companion.apk").exists()
    assert (output_dir / "Elabs-public-site.zip").exists()
    assert json.loads(manifest_output.read_text(encoding="utf-8"))["required_artifact_kinds"] == [
        "wrapper",
        "android",
        "public",
    ]


def test_package_release_artifacts_excludes_generated_dependency_dirs(tmp_path, monkeypatch):
    wrapper, android, public = _write_build_sources(tmp_path)
    output_dir = tmp_path / "release-packages"
    monkeypatch.setenv("AIBENCHIE_RELEASE_ATTESTATION_SECRET", TEST_SIGNING_SECRET)

    package_release_artifacts(
        wrapper_source=wrapper,
        android_source=android,
        public_source=public,
        output_dir=output_dir,
    )

    with zipfile.ZipFile(output_dir / "nullxoid-wrapper.zip") as archive:
        wrapper_names = set(archive.namelist())
    with zipfile.ZipFile(output_dir / "Elabs-public-site.zip") as archive:
        public_names = set(archive.namelist())

    assert "index.html" in wrapper_names
    assert "assets/app.js" in wrapper_names
    assert "node_modules/ignored/junk.js" not in wrapper_names
    assert "content/verdicts/aibenchie-release-artifact-freeze-summary.json" not in public_names


def test_package_release_artifacts_cli(tmp_path, capsys, monkeypatch):
    wrapper, android, public = _write_build_sources(tmp_path)
    output_dir = tmp_path / "release-packages"
    monkeypatch.setenv("AIBENCHIE_RELEASE_ATTESTATION_SECRET", TEST_SIGNING_SECRET)

    exit_code = aibenchie_local.main(
        [
            "--package-release-artifacts",
            "--wrapper-package",
            str(wrapper),
            "--android-package",
            str(android),
            "--public-package",
            str(public),
            "--release-package-output-dir",
            str(output_dir),
            "--release-artifact-key-id",
            "bundle-test-key",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["release_artifacts"] == str(output_dir / "release-artifacts.json")
    assert (output_dir / "nullxoid-wrapper.zip").exists()
