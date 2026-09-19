"""Focused production document-binding checks through the existing native probe."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("AIBENCHIE_CANVAS_NATIVE_PROBE"), reason="Native Windows probe required")


@pytest.fixture
def native(tmp_path):
    with (tmp_path / "native.stderr").open("w") as errors:
        process = subprocess.Popen([os.environ["AIBENCHIE_CANVAS_NATIVE_PROBE"]],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True, encoding="utf-8")
        replies = queue.Queue()
        def read():
            for line in process.stdout:
                replies.put(json.loads(line))
            replies.put(None)
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        def call(action, **body):
            process.stdin.write(json.dumps(dict(action=action, **body)) + "\n")
            process.stdin.flush()
            result = replies.get(timeout=30)
            assert result is not None, "Native probe exited"
            return result
        try:
            yield call
        finally:
            if process.poll() is None:
                process.stdin.write('{"action":"exit"}\n')
                process.stdin.flush()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            reader.join(timeout=2)


def create(native):
    result = native("canvas-create", name="generated.txt", text="Initial\n", workspace="workspace", resource="standard")
    assert result["ok"], result["error"]
    assert result["canvas"]["testOnlyAdapter"] is False
    return result["canvas"]["documents"][0]


def test_save_reopen_and_revocation(native):
    doc = create(native)
    path = Path(doc["path"])
    assert path.read_text() == "Initial\n"
    dirty = native("canvas-edit", id=doc["id"], text="Saved locally\n")
    assert dirty["canvas"]["unsaved"] and not dirty["canvas"]["documents"][0]["canWrite"]
    result = native("canvas-save", id=doc["id"], path=str(path))
    assert result["ok"] and not result["canvas"]["unsaved"], result["error"]
    assert path.read_text() == "Saved locally\n"
    native("canvas-detach", id=doc["id"])
    assert not native("canvas-open", path=str(path))["ok"], "Detach must revoke rather than reopen implicitly"
    assert native("register-files", files=[dict(workspace="workspace", resource="standard", path=str(path), writable=True)])["ok"]
    result = native("canvas-open", path=str(path))
    assert result["ok"], result["error"]
    assert result["canvas"]["documents"][-1]["text"] == "Saved locally\n"
    native("revoke-files")
    reopened_id = result["canvas"]["documents"][-1]["id"]
    native("canvas-edit", id=reopened_id, text="Should not save\n")
    assert not native("canvas-save", id=reopened_id, path=str(path))["ok"]
    assert path.read_text() == "Saved locally\n"


def test_context_and_dirty_reconciliation_preserve_draft(native):
    doc = create(native)
    native("canvas-edit", id=doc["id"], text="Local unsaved\n")
    result = native("canvas-reconcile", path=doc["path"])
    assert not result["ok"] and result["canvas"]["documents"][0]["text"] == "Local unsaved\n"
    native("canvas-context", context="another-account")
    assert not native("canvas-save", id=doc["id"], path=doc["path"])["ok"]
    assert Path(doc["path"]).read_text() == "Initial\n"


def test_same_name_replacement_cannot_be_saved_or_reconciled(native):
    doc = create(native)
    path = Path(doc["path"])
    replacement = path.with_suffix(".replacement")
    replacement.write_text("Replacement must stay unchanged\n", encoding="utf-8")
    path.rename(path.with_suffix(".original"))
    assert not native("create-local-file", path=str(path), text="Implicit reselection")["ok"]
    replacement.rename(path)
    assert not native("canvas-reconcile", path=str(path))["ok"]
    native("canvas-edit", id=doc["id"], text="Overwrite attempted\n")
    assert not native("canvas-save", id=doc["id"], path=str(path))["ok"]
    assert path.read_text() == "Replacement must stay unchanged\n"


def test_new_file_never_overwrites_and_keeps_existing_scope(native, tmp_path):
    target = tmp_path / "existing.txt"
    target.write_text("Keep this\n", encoding="utf-8")
    assert not native("create-local-file", path=str(target), text="Replace it")["ok"]
    assert target.read_text() == "Keep this\n"
    target = tmp_path / "new.txt"
    assert native("create-local-file", path=str(target), text="New local document\n")["ok"]
    assert target.read_text() == "New local document\n"
    assert not native("create-local-file", path=str(tmp_path / "bad.txt:stream"), text="Denied")["ok"]
    assert not native("create-local-file", path=str(tmp_path / "CON.txt"), text="Denied")["ok"]
