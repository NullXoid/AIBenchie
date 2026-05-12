from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - exercised on hosts without psutil
    psutil = None


TELEMETRY_SCHEMA = "aibenchie.resource-telemetry.v1"
MIB = 1024 * 1024


@dataclass
class MonitoredCommandResult:
    command: list[str]
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    resource_telemetry: dict[str, Any]


def run_monitored_command(
    command: list[str],
    *,
    cwd: str | Path,
    sample_interval_seconds: float = 0.5,
) -> MonitoredCommandResult:
    cwd_path = Path(cwd).resolve()
    started_at = now_utc()
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=cwd_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    process_handle = _process_handle(process.pid)
    _prime_cpu(process_handle)
    samples: list[dict[str, Any]] = []
    samples.append(sample_resources(process_handle, elapsed_seconds=0.0))

    while process.poll() is None:
        time.sleep(sample_interval_seconds)
        samples.append(sample_resources(process_handle, elapsed_seconds=time.monotonic() - started))

    stdout, stderr = process.communicate()
    samples.append(sample_resources(process_handle, elapsed_seconds=time.monotonic() - started))
    finished_at = now_utc()
    duration = round(time.monotonic() - started, 3)
    telemetry = {
        "schema": TELEMETRY_SCHEMA,
        "command": command,
        "cwd": str(cwd_path),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration,
        "sample_interval_seconds": sample_interval_seconds,
        "sample_count": len(samples),
        "summary": summarize_samples(samples, duration_seconds=duration),
        "samples": samples,
    }
    return MonitoredCommandResult(
        command=command,
        cwd=str(cwd_path),
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
        resource_telemetry=telemetry,
    )


def sample_resources(process_handle: Any, *, elapsed_seconds: float) -> dict[str, Any]:
    return {
        "observed_at": now_utc(),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "cpu": cpu_snapshot(process_handle),
        "memory": memory_snapshot(process_handle),
        "gpu": gpu_snapshot(),
    }


def cpu_snapshot(process_handle: Any) -> dict[str, Any]:
    if psutil is None:
        return {"available": False, "failure": "psutil_unavailable"}
    process_percent = _process_cpu_percent(process_handle)
    return {
        "available": True,
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "system_percent": psutil.cpu_percent(interval=None),
        "process_percent": process_percent,
        "process_seconds": _process_cpu_seconds(process_handle),
    }


def memory_snapshot(process_handle: Any) -> dict[str, Any]:
    if psutil is None:
        return {"available": False, "failure": "psutil_unavailable"}
    memory = psutil.virtual_memory()
    return {
        "available": True,
        "system_total_mb": round(memory.total / MIB, 2),
        "system_available_mb": round(memory.available / MIB, 2),
        "system_used_percent": memory.percent,
        "process_rss_mb": round(_process_rss_bytes(process_handle) / MIB, 2),
    }


def gpu_snapshot() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"available": False, "provider": "nvidia-smi", "failure": "nvidia_smi_not_found", "gpus": []}
    try:
        completed = subprocess.run(
            [
                executable,
                "--query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "provider": "nvidia-smi", "failure": type(exc).__name__, "gpus": []}
    if completed.returncode != 0:
        return {
            "available": False,
            "provider": "nvidia-smi",
            "failure": "nvidia_smi_failed",
            "stderr": completed.stderr.strip()[:240],
            "gpus": [],
        }
    gpus = parse_nvidia_smi_csv(completed.stdout)
    return {"available": bool(gpus), "provider": "nvidia-smi", "failure": "" if gpus else "gpu_not_reported", "gpus": gpus}


def parse_nvidia_smi_csv(output: str) -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 6:
            continue
        gpus.append(
            {
                "index": _int_or_none(parts[0]),
                "name": parts[1],
                "utilization_gpu_percent": _int_or_none(parts[2]),
                "utilization_memory_percent": _int_or_none(parts[3]),
                "memory_used_mb": _int_or_none(parts[4]),
                "memory_total_mb": _int_or_none(parts[5]),
            }
        )
    return gpus


def summarize_samples(samples: list[dict[str, Any]], *, duration_seconds: float) -> dict[str, Any]:
    cpu_process = _numbers(sample.get("cpu", {}).get("process_percent") for sample in samples)
    cpu_system = _numbers(sample.get("cpu", {}).get("system_percent") for sample in samples)
    cpu_seconds = _numbers(sample.get("cpu", {}).get("process_seconds") for sample in samples)
    memory_process = _numbers(sample.get("memory", {}).get("process_rss_mb") for sample in samples)
    memory_system = _numbers(sample.get("memory", {}).get("system_used_percent") for sample in samples)
    gpu_utilization: list[float] = []
    gpu_memory: list[float] = []
    gpu_available = False
    for sample in samples:
        gpu = sample.get("gpu", {})
        gpu_available = gpu_available or bool(gpu.get("available"))
        for item in gpu.get("gpus") or []:
            if item.get("utilization_gpu_percent") is not None:
                gpu_utilization.append(float(item["utilization_gpu_percent"]))
            if item.get("memory_used_mb") is not None:
                gpu_memory.append(float(item["memory_used_mb"]))

    return {
        "duration_seconds": duration_seconds,
        "sample_count": len(samples),
        "cpu": {
            "process_percent_peak": max(cpu_process) if cpu_process else None,
            "system_percent_peak": max(cpu_system) if cpu_system else None,
            "process_seconds_total": max(cpu_seconds) if cpu_seconds else None,
        },
        "memory": {
            "process_rss_mb_peak": max(memory_process) if memory_process else None,
            "system_used_percent_peak": max(memory_system) if memory_system else None,
        },
        "gpu": {
            "available": gpu_available,
            "utilization_gpu_percent_peak": max(gpu_utilization) if gpu_utilization else None,
            "memory_used_mb_peak": max(gpu_memory) if gpu_memory else None,
        },
    }


def write_resource_telemetry(path: str | Path, telemetry: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json_dumps(telemetry), encoding="utf-8")
    return output


def json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _process_handle(pid: int) -> Any:
    if psutil is None:
        return None
    try:
        return psutil.Process(pid)
    except psutil.Error:
        return None


def _prime_cpu(process_handle: Any) -> None:
    if psutil is None:
        return
    psutil.cpu_percent(interval=None)
    for process in _processes(process_handle):
        try:
            process.cpu_percent(interval=None)
        except psutil.Error:
            continue


def _processes(process_handle: Any) -> list[Any]:
    if psutil is None or process_handle is None:
        return []
    processes = []
    try:
        processes.append(process_handle)
        processes.extend(process_handle.children(recursive=True))
    except psutil.Error:
        return processes
    return processes


def _process_cpu_percent(process_handle: Any) -> float | None:
    if psutil is None or process_handle is None:
        return None
    total = 0.0
    seen = False
    for process in _processes(process_handle):
        try:
            total += float(process.cpu_percent(interval=None))
            seen = True
        except psutil.Error:
            continue
    return round(total, 2) if seen else None


def _process_cpu_seconds(process_handle: Any) -> float | None:
    if psutil is None or process_handle is None:
        return None
    total = 0.0
    seen = False
    for process in _processes(process_handle):
        try:
            times = process.cpu_times()
            total += float(times.user) + float(times.system)
            seen = True
        except psutil.Error:
            continue
    return round(total, 3) if seen else None


def _process_rss_bytes(process_handle: Any) -> int:
    total = 0
    for process in _processes(process_handle):
        try:
            total += int(process.memory_info().rss)
        except Exception:
            continue
    return total


def _numbers(values: Any) -> list[float]:
    numbers: list[float] = []
    for value in values:
        if value is None:
            continue
        try:
            numbers.append(float(value))
        except (TypeError, ValueError):
            continue
    return numbers


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
