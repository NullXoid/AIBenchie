from __future__ import annotations

import json
import zipfile

import aibenchie_local
from aibenchie.distribution_hygiene import run_distribution_hygiene_check


def test_distribution_hygiene_passes_public_safe_repo(tmp_path):
    public = tmp_path / "public_export" / "manifest.json"
    public.parent.mkdir(parents=True)
    public.write_text(json.dumps({"name": "safe-public-export"}), encoding="utf-8")
    (tmp_path / ".env.example").write_text("TOKEN=example-token\n", encoding="utf-8")

    result = run_distribution_hygiene_check(root=tmp_path)

    assert result.ok is True
    assert result.findings == []
    assert result.scanned_files == 2


def test_distribution_hygiene_blocks_private_runtime_owner_data(tmp_path):
    raw_audio = tmp_path / "_runtime" / "private" / "mic.wav"
    raw_audio.parent.mkdir(parents=True)
    raw_audio.write_bytes(b"RIFF")

    result = run_distribution_hygiene_check(root=tmp_path)

    assert result.ok is False
    assert {finding.rule for finding in result.findings} >= {"private_runtime_path", "raw_owner_media"}


def test_distribution_hygiene_blocks_secret_literals(tmp_path):
    config = tmp_path / "public_export" / "release-manifest.json"
    config.parent.mkdir(parents=True)
    secret_value = "-".join(["live", "secret", "value", "that", "should", "not", "ship"])
    config.write_text(
        json.dumps(
            {
                "api_key": secret_value,
                "path": "C:" + "\\Users\\" + "ka" + "som" + "\\projects\\Lv-7\\_runtime\\private",
            }
        ),
        encoding="utf-8",
    )

    result = run_distribution_hygiene_check(root=tmp_path)

    assert result.ok is False
    assert {finding.rule for finding in result.findings} == {"local_machine_path", "secret_literal"}


def test_distribution_hygiene_blocks_secret_files(tmp_path):
    key = tmp_path / "release" / "signing.pem"
    key.parent.mkdir(parents=True)
    private_key_marker = "-----BEGIN " + "PRIVATE KEY-----"
    key.write_text(f"{private_key_marker}\nnot-real\n", encoding="utf-8")

    result = run_distribution_hygiene_check(root=tmp_path)

    assert result.ok is False
    assert {finding.rule for finding in result.findings} >= {"secret_file", "private_key_material"}


def test_distribution_hygiene_scans_zip_packages(tmp_path):
    package = tmp_path / "release.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("app/app.json", "{}")
        archive.writestr("_runtime/private/transcript.txt", "owner transcript")

    result = run_distribution_hygiene_check(root=tmp_path / "empty", packages=[package])

    assert result.ok is False
    assert result.scanned_packages == 1
    assert any(finding.source == "package" and finding.rule == "private_runtime_path" for finding in result.findings)


def test_distribution_hygiene_cli_outputs_json(tmp_path, capsys):
    (tmp_path / "public_export").mkdir()
    (tmp_path / "public_export" / "manifest.json").write_text("{}", encoding="utf-8")

    code = aibenchie_local.main(["--distribution-hygiene", "--distribution-hygiene-root", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["scanned_files"] == 1
