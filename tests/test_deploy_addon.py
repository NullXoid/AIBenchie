from __future__ import annotations

import json

import aibenchie_local
from aibenchie.deploy_addon import execute_deploy_addon, run_deploy_addon_check, verify_deploy_plan
from aibenchie.release_bundle import package_release_artifacts


TEST_SIGNING_SECRET = "test-deploy-addon-secret"


def _write_build_sources(tmp_path):
    wrapper = tmp_path / "wrapper-dist"
    public = tmp_path / "public-dist"
    android = tmp_path / "android" / "app-release.apk"

    (wrapper / "assets").mkdir(parents=True)
    (public / "assets").mkdir(parents=True)
    android.parent.mkdir(parents=True)

    (wrapper / "index.html").write_text("<main>Wrapper</main>\n", encoding="utf-8")
    (wrapper / "assets" / "app.js").write_text("console.log('wrapper')\n", encoding="utf-8")
    (public / "index.html").write_text("<main>Public site</main>\n", encoding="utf-8")
    (public / "assets" / "site.css").write_text("body { color: #fff; }\n", encoding="utf-8")
    android.write_bytes(b"fake apk bytes")
    return wrapper, android, public


def _write_release_artifacts(tmp_path, monkeypatch):
    wrapper, android, public = _write_build_sources(tmp_path)
    output_dir = tmp_path / "release-packages"
    manifest_output = output_dir / "release-artifacts.json"
    monkeypatch.setenv("AIBENCHIE_RELEASE_ATTESTATION_SECRET", TEST_SIGNING_SECRET)
    package_release_artifacts(
        wrapper_source=wrapper,
        android_source=android,
        public_source=public,
        output_dir=output_dir,
        manifest_output=manifest_output,
        signing_key_id="deploy-addon-test-key",
    )
    return manifest_output


def _write_config(tmp_path, release_artifacts, suite_verdict, overrides=None):
    config = {
        "schema": "aibenchie.deploy-addon.v1",
        "dry_run": True,
        "provider": {
            "type": "forgejo",
            "base_url": "https://git.example.test",
            "repository": "EchoLabs/NullXoid",
        },
        "auth": {
            "token_env": "AIBENCHIE_DEPLOY_PROVIDER_TOKEN",
        },
        "release": {
            "tag": "v1.2.3",
            "name": "EchoLabs Suite v1.2.3",
            "prerelease": True,
        },
        "evidence": {
            "suite_verdict": str(suite_verdict),
            "release_artifacts": str(release_artifacts),
        },
    }
    if overrides:
        for key, value in overrides.items():
            config[key] = value
    config_path = tmp_path / "deploy-addon.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def test_deploy_addon_accepts_verified_attested_release(tmp_path, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": True, "verdict": "pass"}), encoding="utf-8")
    config_path = _write_config(tmp_path, release_artifacts, suite_verdict)

    result = run_deploy_addon_check(config_path=config_path).as_dict()

    assert result["ok"] is True
    assert result["provider"] == "forgejo"
    assert result["deploy_plan"]["dry_run"] is True
    assert result["deploy_plan"]["asset_root"] == str(release_artifacts.parent.resolve())
    assert {asset["kind"] for asset in result["deploy_plan"]["assets"]} == {"wrapper", "android", "public"}


def test_deploy_addon_blocks_committed_provider_secret(tmp_path, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": True, "verdict": "pass"}), encoding="utf-8")
    config_path = _write_config(
        tmp_path,
        release_artifacts,
        suite_verdict,
        overrides={"auth": {"token": "ghp_committedsecret"}},
    )

    result = run_deploy_addon_check(config_path=config_path).as_dict()
    secret_check = next(check for check in result["checks"] if check["name"] == "secret_boundary")

    assert result["ok"] is False
    assert secret_check["ok"] is False
    assert "secret_key_not_allowed" in secret_check["failure"]


def test_deploy_addon_blocks_failed_suite_verdict(tmp_path, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": False, "verdict": "blocked"}), encoding="utf-8")
    config_path = _write_config(tmp_path, release_artifacts, suite_verdict)

    result = run_deploy_addon_check(config_path=config_path).as_dict()
    suite_check = next(check for check in result["checks"] if check["name"] == "suite_verdict")

    assert result["ok"] is False
    assert suite_check["failure"] == "suite_verdict_blocking:blocked"


def test_deploy_addon_cli(tmp_path, capsys, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": True, "verdict": "green"}), encoding="utf-8")
    config_path = _write_config(tmp_path, release_artifacts, suite_verdict)

    exit_code = aibenchie_local.main(["--deploy-addon", "--deploy-addon-config", str(config_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["release_tag"] == "v1.2.3"


def test_deploy_addon_cli_writes_sanitized_plan_output(tmp_path, capsys, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": True, "verdict": "green"}), encoding="utf-8")
    config_path = _write_config(tmp_path, release_artifacts, suite_verdict)
    plan_output = tmp_path / "local" / "deploy-plan.json"

    exit_code = aibenchie_local.main(
        [
            "--deploy-addon",
            "--deploy-addon-config",
            str(config_path),
            "--deploy-addon-plan-output",
            str(plan_output),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    plan = json.loads(plan_output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["deploy_plan_written"] is True
    assert payload["deploy_plan_output"] == str(plan_output.resolve())
    assert plan["schema"] == "aibenchie.deploy-plan.v1"
    assert plan["provider"]["repository"] == "EchoLabs/NullXoid"
    assert {asset["kind"] for asset in plan["assets"]} == {"wrapper", "android", "public"}
    plan_text = json.dumps(plan).lower()
    assert "aibenchie_deploy_provider_token" not in plan_text
    assert "ghp_" not in plan_text


def test_deploy_addon_cli_does_not_write_plan_when_gate_fails(tmp_path, capsys, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": False, "verdict": "blocked"}), encoding="utf-8")
    config_path = _write_config(tmp_path, release_artifacts, suite_verdict)
    plan_output = tmp_path / "local" / "deploy-plan.json"

    exit_code = aibenchie_local.main(
        [
            "--deploy-addon",
            "--deploy-addon-config",
            str(config_path),
            "--deploy-addon-plan-output",
            str(plan_output),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["deploy_plan_written"] is False
    assert not plan_output.exists()


def test_deploy_addon_executor_blocks_without_exact_confirmation(tmp_path, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": True, "verdict": "green"}), encoding="utf-8")
    config_path = _write_config(tmp_path, release_artifacts, suite_verdict, overrides={"dry_run": False})
    monkeypatch.setenv("AIBENCHIE_DEPLOY_PROVIDER_TOKEN", "runtime-token")

    result = execute_deploy_addon(config_path=config_path, publish_confirm="wrong-tag").as_dict()

    assert result["ok"] is False
    assert result["published"] is False
    checks = {check["name"]: check for check in result["checks"]}
    assert checks["publish_confirmation"]["ok"] is False
    assert checks["runtime_token"]["ok"] is True


def test_deploy_addon_executor_blocks_dry_run_plan(tmp_path, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": True, "verdict": "green"}), encoding="utf-8")
    config_path = _write_config(tmp_path, release_artifacts, suite_verdict)
    monkeypatch.setenv("AIBENCHIE_DEPLOY_PROVIDER_TOKEN", "runtime-token")

    result = execute_deploy_addon(config_path=config_path, publish_confirm="v1.2.3").as_dict()

    assert result["ok"] is False
    assert result["published"] is False
    checks = {check["name"]: check for check in result["checks"]}
    assert checks["plan_is_not_dry_run"]["failure"] == "plan_is_dry_run"


def test_deploy_addon_executor_publishes_release_and_assets(tmp_path, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": True, "verdict": "green"}), encoding="utf-8")
    config_path = _write_config(tmp_path, release_artifacts, suite_verdict, overrides={"dry_run": False})
    monkeypatch.setenv("AIBENCHIE_DEPLOY_PROVIDER_TOKEN", "runtime-token")
    requests = []

    def fake_request(method, url, **kwargs):
        requests.append(
            {
                "method": method,
                "url": url,
                "token": kwargs["token"],
                "payload": kwargs.get("payload"),
                "data_length": len(kwargs.get("data") or b""),
            }
        )
        if method == "GET":
            return 404, {"message": "not found"}
        if kwargs.get("payload"):
            return 201, {"id": 42, "upload_url": "https://uploads.example.test/repos/EchoLabs/NullXoid/releases/42/assets{?name,label}"}
        return 201, {"ok": True}

    result = execute_deploy_addon(
        config_path=config_path,
        publish_confirm="v1.2.3",
        request_json=fake_request,
    ).as_dict()

    assert result["ok"] is True
    assert result["published"] is True
    assert requests[0]["method"] == "GET"
    assert requests[0]["url"] == "https://git.example.test/api/v1/repos/EchoLabs/NullXoid/releases/tags/v1.2.3"
    assert requests[1]["method"] == "POST"
    assert requests[1]["url"] == "https://git.example.test/api/v1/repos/EchoLabs/NullXoid/releases"
    assert requests[1]["payload"]["tag_name"] == "v1.2.3"
    assert requests[1]["token"] == "runtime-token"
    assert len(requests) == 5
    assert all(request["data_length"] > 0 for request in requests[2:])


def test_deploy_addon_executor_blocks_existing_release_tag(tmp_path, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": True, "verdict": "green"}), encoding="utf-8")
    config_path = _write_config(tmp_path, release_artifacts, suite_verdict, overrides={"dry_run": False})
    monkeypatch.setenv("AIBENCHIE_DEPLOY_PROVIDER_TOKEN", "runtime-token")
    requests = []

    def fake_request(method, url, **kwargs):
        requests.append({"method": method, "url": url, "payload": kwargs.get("payload")})
        if method == "GET":
            return 200, {"id": 42, "tag_name": "v1.2.3"}
        raise AssertionError("release create should not run when tag already exists")

    result = execute_deploy_addon(
        config_path=config_path,
        publish_confirm="v1.2.3",
        request_json=fake_request,
    ).as_dict()

    assert result["ok"] is False
    assert result["published"] is False
    checks = {check["name"]: check for check in result["checks"]}
    assert checks["provider_publish"]["failure"] == "release_tag_already_exists"
    assert result["evidence"][0]["operation"] == "check_release_absent"
    assert requests == [
        {
            "method": "GET",
            "url": "https://git.example.test/api/v1/repos/EchoLabs/NullXoid/releases/tags/v1.2.3",
            "payload": None,
        }
    ]


def test_deploy_addon_executor_blocks_attestation_drift_before_publish(tmp_path, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": True, "verdict": "green"}), encoding="utf-8")
    config_path = _write_config(tmp_path, release_artifacts, suite_verdict, overrides={"dry_run": False})
    monkeypatch.setenv("AIBENCHIE_DEPLOY_PROVIDER_TOKEN", "runtime-token")
    package = release_artifacts.parent / "nullxoid-wrapper.zip"
    package.write_bytes(b"modified after attestation")

    def fake_request(_method, _url, **_kwargs):
        raise AssertionError("provider request should not run after attestation drift")

    result = execute_deploy_addon(
        config_path=config_path,
        publish_confirm="v1.2.3",
        request_json=fake_request,
    ).as_dict()

    assert result["ok"] is False
    assert result["published"] is False
    checks = {check["name"]: check for check in result["checks"]}
    assert checks["release_attestation"]["ok"] is False
    assert checks["publish_gate_passed"]["ok"] is False


def test_deploy_addon_executor_cli(tmp_path, capsys, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": True, "verdict": "green"}), encoding="utf-8")
    config_path = _write_config(tmp_path, release_artifacts, suite_verdict)

    exit_code = aibenchie_local.main(
        [
            "--execute-deploy-addon",
            "--deploy-addon-config",
            str(config_path),
            "--deploy-publish-confirm",
            "v1.2.3",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["published"] is False
    assert any(check["name"] == "runtime_token" for check in payload["checks"])


def test_verify_deploy_plan_accepts_saved_sanitized_plan(tmp_path, capsys, monkeypatch):
    release_artifacts = _write_release_artifacts(tmp_path, monkeypatch)
    suite_verdict = tmp_path / "suite-verdict.json"
    suite_verdict.write_text(json.dumps({"ok": True, "verdict": "green"}), encoding="utf-8")
    config_path = _write_config(tmp_path, release_artifacts, suite_verdict)
    plan_output = tmp_path / "local" / "deploy-plan.json"
    assert (
        aibenchie_local.main(
            [
                "--deploy-addon",
                "--deploy-addon-config",
                str(config_path),
                "--deploy-addon-plan-output",
                str(plan_output),
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()

    result = verify_deploy_plan(plan_output).as_dict()

    assert result["ok"] is True
    assert result["deploy_plan"]["schema"] == "aibenchie.deploy-plan.v1"
    assert {check["name"]: check["ok"] for check in result["checks"]}["secret_boundary"] is True


def test_verify_deploy_plan_blocks_secret_like_values(tmp_path):
    plan = {
        "schema": "aibenchie.deploy-plan.v1",
        "dry_run": True,
        "provider": {
            "type": "github",
            "base_url": "https://github.com",
            "repository": "EchoLabs/NullXoid",
        },
        "release": {
            "tag": "v1.2.3",
            "name": "EchoLabs Suite v1.2.3",
            "prerelease": True,
        },
        "assets": [
            {"kind": "wrapper", "name": "wrapper", "path": "wrapper.zip", "sha256": "a" * 64},
            {"kind": "android", "name": "android", "path": "app.apk", "sha256": "b" * 64},
            {"kind": "public", "name": "public", "path": "site.zip", "sha256": "c" * 64},
        ],
        "provider_token": "ghp_committedsecret",
    }
    plan_path = tmp_path / "deploy-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result = verify_deploy_plan(plan_path).as_dict()
    secret_check = next(check for check in result["checks"] if check["name"] == "secret_boundary")

    assert result["ok"] is False
    assert secret_check["ok"] is False
    assert "secret_key_not_allowed" in secret_check["failure"]


def test_verify_deploy_plan_cli(tmp_path, capsys):
    plan = {
        "schema": "aibenchie.deploy-plan.v1",
        "dry_run": True,
        "provider": {
            "type": "forgejo",
            "base_url": "https://git.example.test",
            "repository": "EchoLabs/NullXoid",
        },
        "release": {
            "tag": "v1.2.3",
            "name": "EchoLabs Suite v1.2.3",
            "prerelease": True,
        },
        "assets": [
            {"kind": "wrapper", "name": "wrapper", "path": "wrapper.zip", "sha256": "a" * 64},
            {"kind": "android", "name": "android", "path": "app.apk", "sha256": "b" * 64},
            {"kind": "public", "name": "public", "path": "site.zip", "sha256": "c" * 64},
        ],
        "requires": [
            "passing_suite_verdict",
            "verified_release_artifact_attestation",
            "runtime_provider_token",
        ],
    }
    plan_path = tmp_path / "deploy-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    exit_code = aibenchie_local.main(["--verify-deploy-plan", "--deploy-plan", str(plan_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["plan_path"] == str(plan_path.resolve())
