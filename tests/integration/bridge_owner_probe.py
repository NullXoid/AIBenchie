"""Test-only diagnostic launcher around the unchanged production pipe endpoint."""
import argparse
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--vault", required=True)
parser.add_argument("--state", required=True)
parser.add_argument("--bridge", required=True)
parser.add_argument("--diagnostics", required=True)
args = parser.parse_args()
sys.path.insert(0, str(Path(args.bridge) / "backend/scripts"))
from nullbridge_owner_pipe import OwnerPipe, build_endpoint
from nullbridge_agent_channel import canonical

def record(message):
    with Path(args.diagnostics).open("a", encoding="utf-8") as output:
        output.write(message + "\n")

try:
    worker, notices, plan = build_endpoint(args.config, args.vault, args.state)
    def observe(client):
        original = client.request
        def request(action, *positional, **named):
            try:
                return original(action, *positional, **named)
            except Exception as exc:
                record(f"{action}: {type(exc).__name__}: {exc}")
                raise
        client.request = request
    observe(worker.http)
    observe(notices)
    def emit(frame):
        sys.stdout.buffer.write(canonical(frame) + b"\n")
        sys.stdout.buffer.flush()
    OwnerPipe(worker, notices, plan, emit).run(sys.stdin.buffer)
except Exception as exc:
    record(f"pipe: {type(exc).__name__}: {exc}")
    sys.stdout.buffer.write(b'{"event":"failed"}\n')
    sys.stdout.buffer.flush()
    raise SystemExit(1)
