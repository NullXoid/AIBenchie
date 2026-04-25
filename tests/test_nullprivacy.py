from __future__ import annotations

import json

import pytest

from aibenchie.nullprivacy import (
    NullPrivacyError,
    decrypt_blob,
    encrypt_blob,
    generate_key,
    run_e2ee_storage_proof,
)


def test_e2ee_blob_roundtrips_without_plaintext_visibility():
    key = generate_key()
    plaintext = b"saved chat private payload"
    envelope = encrypt_blob(key, plaintext, associated_data={"target": "saved_chats"})
    serialized = json.dumps(envelope, sort_keys=True).encode("utf-8")

    assert plaintext not in serialized
    assert decrypt_blob(key, envelope) == plaintext


def test_e2ee_blob_rejects_wrong_key_and_tampering():
    key = generate_key()
    wrong_key = generate_key()
    envelope = encrypt_blob(key, b"private artifact payload")

    with pytest.raises(NullPrivacyError, match="authentication failed"):
        decrypt_blob(wrong_key, envelope)

    tampered = dict(envelope)
    tampered["tag"] = envelope["tag"][:-2] + "AA"
    with pytest.raises(NullPrivacyError, match="authentication failed"):
        decrypt_blob(key, tampered)


def test_e2ee_storage_proof_reports_release_gate_shape():
    proof = run_e2ee_storage_proof()
    payload = proof.as_dict()

    assert payload["ok"] is True
    assert payload["roundtrip_ok"] is True
    assert payload["wrong_key_rejected"] is True
    assert payload["tamper_rejected"] is True
    assert payload["plaintext_visible_in_blob"] is False
