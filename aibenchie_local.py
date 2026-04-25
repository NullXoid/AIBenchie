from __future__ import annotations

import argparse
import json
import sys

from aibenchie.local_ollama import DEFAULT_OLLAMA_URL, benchmark_ollama_model, list_ollama_models, model_name


DEFAULT_PROMPT = "Reply with one sentence explaining what AIBenchie verifies before a release."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run public-safe local AIBenchie checks.")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Local Ollama URL. Only localhost URLs are allowed.")
    parser.add_argument("--model", default="", help="Model to test. Defaults to the first detected model.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Bounded prompt for the local model test.")
    parser.add_argument("--list-models", action="store_true", help="List detected local Ollama models and exit.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    models = list_ollama_models(args.ollama_url)
    model_names = [model_name(item) for item in models if model_name(item)]

    if args.list_models:
        payload = {"ollama_url": args.ollama_url, "model_count": len(model_names), "models": model_names}
        print(json.dumps(payload, indent=2) if args.json else "\n".join(model_names))
        return 0

    selected = args.model or (model_names[0] if model_names else "")
    if not selected:
        raise SystemExit("Ollama responded, but no models were listed.")

    result = benchmark_ollama_model(args.ollama_url, selected, args.prompt)
    result["model_count"] = len(model_names)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Model: {result['model']}")
        print(f"Latency: {result['elapsed_seconds']}s")
        print(f"Tokens/sec: {result['tokens_per_second']}")
        print(f"Response: {result['response']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
