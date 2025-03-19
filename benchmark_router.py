# benchmark_router.py
# Description: Benchmarks locally installed Ollama models using smart_model_router or direct API with tier-based context limits. Can be triggered standalone or via assistant, with optional metadata logging and CLI support. Includes modes: single model, benchmark all, and head-to-head.

import time
import requests
from datetime import datetime
from rich import print
from rich.prompt import Prompt
from smart_model_router import smart_model_router
from utils.tier_control import get_user_trust_tier
import os
import subprocess
import re
import argparse

OLLAMA_API_URL = "http://localhost:11434/api/generate"
BENCHMARK_DIR = "benchmarks"
os.makedirs(BENCHMARK_DIR, exist_ok=True)

UTILITY_SCRIPTS = {
    "benchmark": "benchmark_router.py",
    "benchmark tool": "benchmark_router.py",
    "vision test": "text_vision_test.py",
    "text vision test": "text_vision_test.py"
}

def get_context_limit():
    tier = (get_user_trust_tier() or "low").lower()
    return {
        "high": 128000,
        "mid": 32000,
        "low": 16000
    }.get(tier, 16000), tier

def list_models():
    try:
        raw = os.popen("ollama list").read().strip().splitlines()[2:]
        return [line.split()[0] for line in raw if line.strip()]
    except Exception as e:
        print(f"[red]Failed to list models:[/red] {e}")
        return []

def benchmark_model(model: str, prompt: str, use_router=False, headless=False):
    print(f"\nBenchmarking: [cyan]{model}[/cyan]{' (via smart_model_router)' if use_router else ''}...")
    start = time.time()

    context_limit, tier = get_context_limit()
    token_count = 0

    if use_router:
        try:
            response = smart_model_router(prompt=prompt, model_hint=model, stream=False)
            if isinstance(response, tuple):
                response = response[0]
            output = response
            token_count = len(output.split()) if output else 0
        except Exception as e:
            print(f"[red]Router error:[/red] {e}")
            return
    else:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": context_limit}
        }
        try:
            res = requests.post(OLLAMA_API_URL, json=payload)
            res.raise_for_status()
            response = res.json()
            output = response.get("response") or response.get("message") or str(response)
            token_count = response.get("eval_count") or len(output.split())
        except Exception as e:
            print(f"[red]API Error:[/red] {e}")
            return

    duration = round(time.time() - start, 2)
    print(f"\n[bold green]Time:[/bold green] {duration}s | [bold yellow]Tokens:[/bold yellow] {token_count}\n")
    print(output[:1000] + ("..." if len(output) > 1000 else ""))

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = model.replace("/", "-").replace(":", "_")
    log_name = f"{BENCHMARK_DIR}/benchmark_{safe_name}_{now}.txt"
    with open(log_name, "w", encoding="utf-8") as f:
        f.write(f"Model: {model}\n")
        f.write(f"Trust Tier: {tier}\n")
        f.write(f"Context Limit: {context_limit}\n")
        f.write(f"Used smart_model_router: {use_router}\n")
        f.write(f"Time: {duration}s\nTokens: {token_count}\n\n")
        f.write(output)
    print(f"[dim]Saved log to {log_name}[/dim]")

def run_external_script(script_name):
    print(f"\n[bold blue]🔧 Running external tool:[/bold blue] {script_name}\n")
    try:
        subprocess.call(["python", script_name])
    except Exception as e:
        print(f"[red]Error running {script_name}:[/red] {e}")

def head_to_head(models, prompt, use_router):
    print("\n🆚 [bold cyan]Head-to-Head Comparison[/bold cyan]")
    outputs = []
    for model in models:
        print(f"\n→ [bold]{model}[/bold]")
        benchmark_model(model, prompt, use_router=use_router)
        print("\n" + "=" * 80)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, help="Model name to benchmark")
    parser.add_argument("--prompt", type=str, help="Prompt text or path to prompt file")
    parser.add_argument("--router", action="store_true", help="Use smart_model_router")
    parser.add_argument("--headless", action="store_true", help="Run in assistant or CLI mode")
    args = parser.parse_args()

    print("\n🚀 [bold]Ollama Model Benchmark v0.02[/bold]")

    if args.model and args.prompt:
        if os.path.isfile(args.prompt):
            try:
                with open(args.prompt, "r", encoding="utf-8") as f:
                    prompt = f.read().strip()
            except Exception as e:
                print(f"[red]Failed to read prompt file:[/red] {e}")
                return
        else:
            prompt = args.prompt
        benchmark_model(args.model, prompt, use_router=args.router, headless=True)
        return

    models = list_models()
    if not models:
        print("[red]No models found.[/red]")
        return

    print("\nAvailable models:")
    for i, m in enumerate(models):
        print(f"[{i}] {m}")

    print("\nSelect mode:")
    print("[1] Single model benchmark")
    print("[2] Benchmark all models")
    print("[3] Head-to-head mode")
    mode = Prompt.ask("Choose a mode", choices=["1", "2", "3"], default="1")

    use_router = Prompt.ask("Use smart_model_router?", choices=["y", "n"], default="n").lower() == "y"

    use_custom = Prompt.ask("Use a custom prompt file?", choices=["y", "n"], default="n").lower() == "y"
    if use_custom:
        path = Prompt.ask("Enter path to prompt file")
        try:
            with open(path, "r", encoding="utf-8") as f:
                prompt = f.read().strip()
        except Exception as e:
            print(f"[red]Failed to read prompt file:[/red] {e}")
            return
    else:
        prompt_type = Prompt.ask("Choose prompt type (text/code/vision)", choices=["text", "code", "vision"], default="text")
        prompt = {
            "text": "What causes a star to become a black hole?",
            "code": "Write a Python function that calculates the factorial of a number using recursion.",
            "vision": "Describe the image content."
        }[prompt_type]

    if mode == "1":
        index = Prompt.ask("\nSelect a model to test (index)", default="0")
        try:
            model = models[int(index)]
        except Exception:
            print("[red]Invalid model index.[/red]")
            return
        benchmark_model(model, prompt, use_router=use_router)

    elif mode == "2":
        for model in models:
            benchmark_model(model, prompt, use_router=use_router)

    elif mode == "3":
        print("\nSelect two models for head-to-head:")
        idx1 = Prompt.ask("Model 1 index")
        idx2 = Prompt.ask("Model 2 index")
        try:
            model1 = models[int(idx1)]
            model2 = models[int(idx2)]
        except Exception:
            print("[red]Invalid model indices.[/red]")
            return
        head_to_head([model1, model2], prompt, use_router=use_router)

if __name__ == "__main__":
    main()
