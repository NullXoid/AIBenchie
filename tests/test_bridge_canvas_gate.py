from aibenchie.bridge_canvas import junit_passed, run
import json
from pathlib import Path


def test_missing_configuration_is_blocked_not_pass(tmp_path):
    result = run(tmp_path / "account", tmp_path / "bridge", tmp_path / "probe.exe", tmp_path / "evidence")
    assert result["verdict"] == "blocked" and result["physicalAcceptance"] is False
    assert set(result["missing"]) == {"account_source", "bridge_source", "native_probe"}


def test_skipped_or_empty_or_failed_execution_never_passes(tmp_path):
    xml = tmp_path / "result.xml"
    for content in ('<testsuites/>', '<testsuites><testcase><skipped/></testcase></testsuites>',
                    '<testsuites><testcase><failure/></testcase></testsuites>', 'invalid'):
        xml.write_text(content)
        assert not junit_passed(xml, 0)
    xml.write_text('<testsuites><testsuite><testcase name="combined-chain"/></testsuite></testsuites>')
    assert junit_passed(xml, 0)
    assert not junit_passed(xml, 1)


def test_manifest_registers_explicit_combined_gate():
    root = Path(__file__).resolve().parents[1]
    path = root / "configs/echolabs_universal_e2e.json"
    manifest = json.loads(path.read_text())
    target = next(t for t in manifest["lanes"]["api"]["targets"] if t["id"] == "bridge-canvas-account-native")
    assert target["adapter"] == "command" and target["required"] is True
    assert (path.parent / target["cwd"]).resolve() == root
    assert target["command"] == ["python", "-m", "aibenchie.bridge_canvas"]
