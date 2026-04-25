from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from typing import Any


ENVELOPE_VERSION = 1
KDF_CONTEXT = b"aibenchie-nullprivacy-e2ee-v1"


class NullPrivacyError(ValueError):
    pass


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def unb64(data: str) -> bytes:
    padded = data + ("=" * (-len(data) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def generate_key() -> bytes:
    return secrets.token_bytes(32)


def derive_keys(master_key: bytes, salt: bytes) -> tuple[bytes, bytes]:
    if len(master_key) < 32:
        raise NullPrivacyError("master key must be at least 32 bytes")
    material = hmac.new(master_key, salt + KDF_CONTEXT, hashlib.sha512).digest()
    return material[:32], material[32:64]


def keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    chunks: list[bytes] = []
    counter = 0
    while sum(len(chunk) for chunk in chunks) < length:
        block = hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        chunks.append(block)
        counter += 1
    return b"".join(chunks)[:length]


def xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def encrypt_blob(master_key: bytes, plaintext: bytes, *, associated_data: dict[str, Any] | None = None) -> dict[str, Any]:
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(16)
    enc_key, mac_key = derive_keys(master_key, salt)
    ciphertext = xor_bytes(plaintext, keystream(enc_key, nonce, len(plaintext)))
    aad = associated_data or {}
    aad_bytes = json.dumps(aad, sort_keys=True, separators=(",", ":")).encode("utf-8")
    tag = hmac.new(mac_key, aad_bytes + salt + nonce + ciphertext, hashlib.sha256).digest()
    return {
        "version": ENVELOPE_VERSION,
        "alg": "AIBenchie-HMAC-Stream-v1",
        "salt": b64(salt),
        "nonce": b64(nonce),
        "aad": aad,
        "ciphertext": b64(ciphertext),
        "tag": b64(tag),
    }


def decrypt_blob(master_key: bytes, envelope: dict[str, Any]) -> bytes:
    if envelope.get("version") != ENVELOPE_VERSION:
        raise NullPrivacyError("unsupported envelope version")
    salt = unb64(str(envelope.get("salt") or ""))
    nonce = unb64(str(envelope.get("nonce") or ""))
    ciphertext = unb64(str(envelope.get("ciphertext") or ""))
    tag = unb64(str(envelope.get("tag") or ""))
    enc_key, mac_key = derive_keys(master_key, salt)
    aad = envelope.get("aad") or {}
    aad_bytes = json.dumps(aad, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected = hmac.new(mac_key, aad_bytes + salt + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise NullPrivacyError("authentication failed")
    return xor_bytes(ciphertext, keystream(enc_key, nonce, len(ciphertext)))


@dataclass(frozen=True)
class E2EEProof:
    ok: bool
    plaintext_visible_in_blob: bool
    wrong_key_rejected: bool
    tamper_rejected: bool
    roundtrip_ok: bool

    def as_dict(self) -> dict[str, bool]:
        return {
            "ok": self.ok,
            "plaintext_visible_in_blob": self.plaintext_visible_in_blob,
            "wrong_key_rejected": self.wrong_key_rejected,
            "tamper_rejected": self.tamper_rejected,
            "roundtrip_ok": self.roundtrip_ok,
        }


def run_e2ee_storage_proof() -> E2EEProof:
    key = generate_key()
    wrong_key = generate_key()
    plaintext = b"private saved chat: release gate proof"
    envelope = encrypt_blob(key, plaintext, associated_data={"target": "saved_chats", "privacy_level": 5})
    serialized = json.dumps(envelope, sort_keys=True).encode("utf-8")
    plaintext_visible = plaintext in serialized

    decrypted = decrypt_blob(key, envelope)
    roundtrip_ok = decrypted == plaintext

    wrong_key_rejected = False
    try:
        decrypt_blob(wrong_key, envelope)
    except NullPrivacyError:
        wrong_key_rejected = True

    tampered = dict(envelope)
    tampered["ciphertext"] = b64(unb64(tampered["ciphertext"])[:-1] + b"\x00")
    tamper_rejected = False
    try:
        decrypt_blob(key, tampered)
    except NullPrivacyError:
        tamper_rejected = True

    ok = roundtrip_ok and wrong_key_rejected and tamper_rejected and not plaintext_visible
    return E2EEProof(
        ok=ok,
        plaintext_visible_in_blob=plaintext_visible,
        wrong_key_rejected=wrong_key_rejected,
        tamper_rejected=tamper_rejected,
        roundtrip_ok=roundtrip_ok,
    )
