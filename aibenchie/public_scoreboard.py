from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCOREBOARD_SCHEMA_VERSION = 1
DEFAULT_SCOREBOARD_OUTPUT = Path("public_export") / "aibenchie-scoreboard.json"
VERSION_RE = re.compile(r"^v(?P<body>\d+(?:_\d+)*)(?P<suffix>[a-z]?)_(?P<name>.+)$", re.IGNORECASE)
SECRET_MARKERS = (
    "authorization",
    "bearer ",
    "cookie",
    "password",
    "private_key",
    "secret",
    "service_token",
    "token",
)
BLOCKED_PATH_MARKERS = (
    "/home/",
    "/root/",
    "\\users\\",
    "127.0.0.1",
    "192.168.",
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
)


@dataclass(frozen=True)
class ScoreboardClass:
    key: str
    title: str
    source: str
    milestone: str
    version: str
    status: str
    result: str
    score: float
    record_count: int | None
    pass_count: int | None
    summary: str
    sort_key: tuple[int, ...]
    suffix_weight: int

    def public_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "key": self.key,
            "title": self.title,
            "source": self.source,
            "milestone": self.milestone,
            "version": self.version,
            "status": self.status,
            "result": self.result,
            "score": round(self.score, 2),
            "summary": self.summary,
        }
        if self.record_count is not None:
            payload["record_count"] = self.record_count
        if self.pass_count is not None:
            payload["pass_count"] = self.pass_count
        return payload


@dataclass
class PublicScoreboardResult:
    ok: bool
    root: str
    output: str
    scoreboard: dict[str, Any]
    included_reports: int
    skipped_reports: int
    failure: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "output": self.output,
            "scoreboard": self.scoreboard,
            "included_reports": self.included_reports,
            "skipped_reports": self.skipped_reports,
            "failure": self.failure,
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _env_path(env: dict[str, str], name: str, default: Path) -> Path:
    raw = env.get(name, "").strip()
    return Path(raw) if raw else default


def _version_parts(stem: str) -> tuple[tuple[int, ...], int, str, str] | None:
    match = VERSION_RE.match(stem)
    if not match:
        return None
    numbers = tuple(int(part) for part in match.group("body").split("_"))
    suffix = match.group("suffix").lower()
    suffix_weight = ord(suffix) - 96 if suffix else 0
    return numbers, suffix_weight, f"v{match.group('body')}{suffix}", match.group("name").lower()


def _title_for_key(key: str) -> str:
    replacements = {
        "sft": "SFT",
        "dpo": "DPO",
        "e2e": "E2E",
        "api": "API",
        "lv7": "Lv-7",
    }
    words = []
    for word in key.replace("-", "_").split("_"):
        words.append(replacements.get(word.lower(), word.capitalize()))
    return " ".join(words)


def _first_text(payload: dict[str, Any], *names: str) -> str:
    for name in names:
        value = payload.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _first_int(payload: dict[str, Any], *names: str) -> int | None:
    for name in names:
        value = payload.get(name)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def _positive_flags(payload: dict[str, Any]) -> bool:
    for name in (
        "accepted",
        "contract_ready",
        "implementation_complete",
        "ok",
        "promotion_complete",
        "promotion_recommended",
        "promoted_by_this_milestone",
        "release_baseline_ready",
        "ready",
    ):
        if payload.get(name) is True:
            return True
    return False


def _classify(status: str, payload: dict[str, Any]) -> str:
    upper = status.upper()
    blocked_markers = ("BLOCKED", "FAIL", "ERROR", "REJECT", "MISSING", "NOT_READY")
    pass_markers = ("PASS", "READY", "ACCEPTED", "PROMOTION", "PROMOTED", "COMPLETE", "IMPLEMENTED")
    if any(marker in upper for marker in blocked_markers):
        return "blocked"
    if _positive_flags(payload) or any(marker in upper for marker in pass_markers):
        return "pass"
    return "review"


def _score_for(result: str, record_count: int | None, pass_count: int | None) -> float:
    if record_count and pass_count is not None and record_count > 0:
        return max(0.0, min(100.0, (pass_count / record_count) * 100))
    if result == "pass":
        return 100.0
    if result == "blocked":
        return 0.0
    return 50.0


def _summary_for(status: str, payload: dict[str, Any]) -> str:
    action = _first_text(payload, "next_recommended_action", "next_action", "recommendation")
    if action:
        return f"{status}. {action}"
    return status


def _public_safe(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True, default=str).lower()
    if any(marker in text for marker in SECRET_MARKERS):
        return False
    normalized = text.replace("\\\\", "\\")
    return not any(marker in normalized for marker in BLOCKED_PATH_MARKERS)


def _load_scoreboard_class(root: Path, path: Path) -> ScoreboardClass | None:
    version = _version_parts(path.stem)
    if version is None:
        return None
    sort_key, suffix_weight, version_label, class_key = version

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    status = _first_text(payload, "status", "verdict", "decision")
    milestone = _first_text(payload, "milestone", "release_id", "suite_id")
    if not status or not milestone:
        return None

    result = _classify(status, payload)
    record_count = _first_int(payload, "runtime_record_count", "trusted_record_count", "record_count", "scenario_count")
    pass_count = _first_int(payload, "runtime_pass_count", "pass_count")
    score = _score_for(result, record_count, pass_count)
    source = path.relative_to(root).as_posix()
    item = ScoreboardClass(
        key=class_key,
        title=_title_for_key(class_key),
        source=source,
        milestone=milestone,
        version=version_label,
        status=status,
        result=result,
        score=score,
        record_count=record_count,
        pass_count=pass_count,
        summary=_summary_for(status, payload),
        sort_key=sort_key,
        suffix_weight=suffix_weight,
    )
    return item if _public_safe(item.public_dict()) else None


def _latest_by_class(items: list[ScoreboardClass]) -> list[ScoreboardClass]:
    latest: dict[str, ScoreboardClass] = {}
    for item in items:
        current = latest.get(item.key)
        if current is None:
            latest[item.key] = item
            continue
        if (item.sort_key, item.suffix_weight, item.source) >= (current.sort_key, current.suffix_weight, current.source):
            latest[item.key] = item
    return sorted(latest.values(), key=lambda item: (item.result != "blocked", item.title.lower()))


def _grade_for(score: float) -> str:
    if score >= 90:
        return "release_candidate"
    if score >= 75:
        return "guarded"
    if score >= 50:
        return "review"
    return "blocked"


def _visual_tracks() -> list[dict[str, str]]:
    return [
        {
            "key": "e2ee_readiness",
            "title": "E2EE readiness",
            "visual_label": "GREEN / PASS",
            "result": "pass",
            "summary": (
                "AIBenchie E2EE readiness is complete for the current evidence boundary and should display as green."
            ),
        },
        {
            "key": "zero_knowledge_privacy",
            "title": "Zero-knowledge privacy",
            "visual_label": "PLANNED",
            "result": "planned",
            "summary": (
                "Future track for user or device held keys where supported private payloads stay unreadable to the backend."
            ),
        },
        {
            "key": "resource_bloat_guardrails",
            "title": "Resource bloat guardrails",
            "visual_label": "YELLOW / PARTIAL",
            "result": "partial",
            "summary": (
                "Budget checks and generated-output policy exist; runtime leases and cleanup jobs are next."
            ),
        },
        {
            "key": "nullbridge_trust_fabric",
            "title": "NullBridge trust fabric",
            "visual_label": "GREEN / PASS",
            "result": "pass",
            "summary": (
                "Signed backend identity, deny-by-default routing, redacted audit, and notification policy gates pass."
            ),
        },
    ]


def build_public_scoreboard(root: Path | None = None) -> tuple[dict[str, Any], int, int]:
    actual_root = (root or _repo_root()).resolve()
    report_dir = actual_root / "reports" / "runtime"
    candidates = sorted(report_dir.glob("*.json")) if report_dir.exists() else []
    loaded: list[ScoreboardClass] = []
    skipped = 0
    for path in candidates:
        item = _load_scoreboard_class(actual_root, path)
        if item is None:
            skipped += 1
        else:
            loaded.append(item)

    classes = _latest_by_class(loaded)
    score = round(sum(item.score for item in classes) / len(classes), 2) if classes else 0.0
    counts = {
        "pass": sum(1 for item in classes if item.result == "pass"),
        "blocked": sum(1 for item in classes if item.result == "blocked"),
        "review": sum(1 for item in classes if item.result == "review"),
    }
    scoreboard = {
        "schema_version": SCOREBOARD_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": "AIBenchie Public Scoreboard",
        "summary": (
            "Public-safe latest valid result per class. Raw runtime reports and benchmark fixtures stay in AIBenchie."
        ),
        "policy": {
            "latest_per_class": True,
            "raw_reports_published": False,
            "raw_data_fixtures_published": False,
            "source": "reports/runtime/*.json",
        },
        "overall": {
            "score": score,
            "grade": _grade_for(score),
            "class_count": len(classes),
            "pass_count": counts["pass"],
            "blocked_count": counts["blocked"],
            "review_count": counts["review"],
        },
        "visual_tracks": _visual_tracks(),
        "classes": [item.public_dict() for item in classes],
    }
    if not _public_safe(scoreboard):
        raise ValueError("public scoreboard contains blocked private or secret-like content")
    return scoreboard, len(loaded), skipped


def write_public_scoreboard(
    *,
    root: Path | None = None,
    output: Path | None = None,
    env: dict[str, str] | None = None,
) -> PublicScoreboardResult:
    source = dict(os.environ if env is None else env)
    actual_root = (root or _repo_root()).resolve()
    output_path = output or _env_path(source, "AIBENCHIE_PUBLIC_SCOREBOARD_OUTPUT", actual_root / DEFAULT_SCOREBOARD_OUTPUT)
    if not output_path.is_absolute():
        output_path = actual_root / output_path

    try:
        scoreboard, included, skipped = build_public_scoreboard(actual_root)
    except ValueError as exc:
        return PublicScoreboardResult(
            ok=False,
            root=str(actual_root),
            output=str(output_path),
            scoreboard={},
            included_reports=0,
            skipped_reports=0,
            failure=str(exc),
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(scoreboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return PublicScoreboardResult(
        ok=True,
        root=str(actual_root),
        output=str(output_path),
        scoreboard=scoreboard,
        included_reports=included,
        skipped_reports=skipped,
    )
