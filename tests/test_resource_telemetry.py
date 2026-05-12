from __future__ import annotations

import sys

from aibenchie.resource_telemetry import parse_nvidia_smi_csv, run_monitored_command, summarize_samples


def test_parse_nvidia_smi_csv_extracts_gpu_usage():
    output = "0, NVIDIA GeForce RTX 4090, 72, 18, 1024, 24564\n"

    gpus = parse_nvidia_smi_csv(output)

    assert gpus == [
        {
            "index": 0,
            "name": "NVIDIA GeForce RTX 4090",
            "utilization_gpu_percent": 72,
            "utilization_memory_percent": 18,
            "memory_used_mb": 1024,
            "memory_total_mb": 24564,
        }
    ]


def test_summarize_samples_reports_cpu_memory_and_gpu_peaks():
    samples = [
        {
            "cpu": {"process_percent": 3.0, "system_percent": 15.0},
            "memory": {"process_rss_mb": 40.0, "system_used_percent": 55.0},
            "gpu": {"available": True, "gpus": [{"utilization_gpu_percent": 12, "memory_used_mb": 256}]},
        },
        {
            "cpu": {"process_percent": 8.0, "system_percent": 17.5},
            "memory": {"process_rss_mb": 45.5, "system_used_percent": 57.0},
            "gpu": {"available": True, "gpus": [{"utilization_gpu_percent": 35, "memory_used_mb": 512}]},
        },
    ]

    summary = summarize_samples(samples, duration_seconds=1.25)

    assert summary["cpu"]["process_percent_peak"] == 8.0
    assert summary["cpu"]["system_percent_peak"] == 17.5
    assert summary["cpu"]["process_seconds_total"] is None
    assert summary["memory"]["process_rss_mb_peak"] == 45.5
    assert summary["memory"]["system_used_percent_peak"] == 57.0
    assert summary["gpu"]["available"] is True
    assert summary["gpu"]["utilization_gpu_percent_peak"] == 35.0
    assert summary["gpu"]["memory_used_mb_peak"] == 512.0


def test_run_monitored_command_records_resource_telemetry(tmp_path):
    result = run_monitored_command(
        [sys.executable, "-c", "print('telemetry-ok')"],
        cwd=tmp_path,
        sample_interval_seconds=0.01,
    )

    telemetry = result.resource_telemetry
    assert result.returncode == 0
    assert result.stdout.strip() == "telemetry-ok"
    assert telemetry["schema"] == "aibenchie.resource-telemetry.v1"
    assert telemetry["sample_count"] >= 1
    assert telemetry["summary"]["duration_seconds"] >= 0
    assert "cpu" in telemetry["summary"]
    assert "memory" in telemetry["summary"]
    assert "gpu" in telemetry["summary"]
