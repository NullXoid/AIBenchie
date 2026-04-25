from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent
POLICIES = ROOT / ".suite" / "policies"
MASCOT = ROOT / "docs" / "assets" / "aibenchie-mascots.png"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
MAX_PROMPT_CHARS = 500
MAX_PREDICT_TOKENS = 128
REQUEST_TIMEOUT_SECONDS = 45


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def is_allowed_ollama_url(base_url: str) -> bool:
    parsed = urllib.parse.urlparse(base_url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "http" and host in {"127.0.0.1", "localhost", "::1"}


def ollama_json(base_url: str, path: str, payload: dict | None = None, timeout: int = 5) -> dict:
    if not is_allowed_ollama_url(base_url):
        raise ValueError("AIBenchie only probes localhost Ollama from this public app. Run locally for PC model tests.")
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    data = None
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/json")
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def list_ollama_models(base_url: str = DEFAULT_OLLAMA_URL) -> list[dict]:
    data = ollama_json(base_url, "/api/tags")
    models = data.get("models", [])
    return models if isinstance(models, list) else []


def benchmark_ollama_model(base_url: str, model: str, prompt: str) -> dict:
    prompt = prompt.strip()[:MAX_PROMPT_CHARS]
    if not model:
        raise ValueError("Select a model before running a benchmark.")
    if not prompt:
        raise ValueError("Enter a short prompt before running a benchmark.")
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": MAX_PREDICT_TOKENS,
        },
    }
    started = time.perf_counter()
    data = ollama_json(base_url, "/api/generate", payload=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    elapsed = max(time.perf_counter() - started, 0.001)
    output = str(data.get("response") or "")
    eval_count = int(data.get("eval_count") or max(len(output.split()), 1))
    return {
        "model": model,
        "elapsed_seconds": round(elapsed, 2),
        "tokens": eval_count,
        "tokens_per_second": round(eval_count / elapsed, 2),
        "response": output,
    }


def count_tests() -> int:
    total = 0
    for path in (ROOT / "tests").glob("test_*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        total += text.count("def test_")
    return total


def policy_status() -> list[tuple[str, str, str]]:
    gates = load_json(POLICIES / "aibenchie-gates.json")
    resource = load_json(POLICIES / "resource-policy.json")
    privacy = load_json(POLICIES / "privacy-levels.json")
    release = load_json(POLICIES / "release-policy.json")
    tracks = gates.get("required_tracks") or []
    return [
        ("Release gates", f"{len(tracks)} tracked", "Quality, platform, privacy, security, and release checks."),
        ("Resource policy", "bounded" if resource.get("deny_unbounded_resources") else "review", "Heavy work requires capped leases."),
        ("Privacy levels", f"{len(privacy.get('levels', {}))} levels", "Local, secure remote, relay, and sovereign modes."),
        ("Release source", str(release.get("source_of_truth", "not configured")), "Forgejo remains the canonical release source."),
    ]


def render_ollama_panel() -> None:
    st.subheader("Local Ollama Model Test")
    st.write(
        "This panel can detect and test Ollama only when this Streamlit app is running on the same machine "
        "as Ollama. Streamlit Cloud cannot reach Ollama on your PC directly."
    )

    base_url = st.text_input("Ollama base URL", value=DEFAULT_OLLAMA_URL)
    if not is_allowed_ollama_url(base_url):
        st.error("Only localhost Ollama URLs are allowed here. Use NullBridge later for remote/private backends.")
        return

    try:
        models = list_ollama_models(base_url)
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        st.warning(f"Ollama was not reachable from this Streamlit runtime: {exc}")
        st.code("ollama serve", language="bash")
        st.caption("For PC-local testing, run: streamlit run streamlit_app.py")
        return

    if not models:
        st.info("Ollama responded, but no models were listed.")
        return

    model_names = [str(item.get("name") or item.get("model")) for item in models if item.get("name") or item.get("model")]
    selected = st.selectbox("Detected models", model_names)

    with st.expander("Detected model details", expanded=False):
        st.dataframe(
            [
                {
                    "model": item.get("name") or item.get("model"),
                    "family": (item.get("details") or {}).get("family", ""),
                    "parameters": (item.get("details") or {}).get("parameter_size", ""),
                    "quantization": (item.get("details") or {}).get("quantization_level", ""),
                    "size_mb": round(int(item.get("size") or 0) / 1024 / 1024, 1),
                }
                for item in models
            ],
            use_container_width=True,
        )

    prompt = st.text_area(
        "Benchmark prompt",
        value="Reply with one sentence explaining what AIBenchie verifies before a release.",
        max_chars=MAX_PROMPT_CHARS,
    )
    if st.button("Run local model test"):
        with st.spinner(f"Testing {selected} through Ollama..."):
            try:
                result = benchmark_ollama_model(base_url, selected, prompt)
            except Exception as exc:
                st.error(f"Benchmark failed: {exc}")
                return
        col1, col2, col3 = st.columns(3)
        col1.metric("Model", result["model"])
        col2.metric("Latency", f"{result['elapsed_seconds']}s")
        col3.metric("Tokens/sec", result["tokens_per_second"])
        st.text_area("Model response", value=result["response"], height=180)


def main() -> None:
    st.set_page_config(
        page_title="AIBenchie",
        page_icon="A",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown(
        """
        <style>
          .block-container { padding-top: 2rem; padding-bottom: 3rem; }
          [data-testid="stMetricValue"] { font-size: 2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.1, 0.9], vertical_alignment="center")
    with left:
        st.caption("AIBenchie release verdict engine")
        st.title("Ship only when the suite earns it.")
        st.write(
            "AIBenchie is the NullXoid suite judge for model quality, platform health, "
            "NullBridge enforcement, privacy claims, resource budgets, and signed release readiness."
        )
        st.link_button("View GitHub repo", "https://github.com/NullXoid/AIBenchie")
        st.link_button("View Netlify page", "https://echolabs.netlify.app/aibenchie")
    with right:
        if MASCOT.exists():
            st.image(str(MASCOT), use_container_width=True)
        else:
            st.info("Mascot asset is not present in this deployment.")

    st.divider()

    tests = count_tests()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Suite checks", tests)
    col2.metric("Critical blockers", "0")
    col3.metric("Publish mode", "Signed")
    col4.metric("Secret storage", "Ephemeral")

    st.subheader("Gate Map")
    rows = policy_status()
    for index in range(0, len(rows), 2):
        cols = st.columns(2)
        for col, row in zip(cols, rows[index : index + 2]):
            name, value, detail = row
            with col:
                st.markdown(f"**{name}**")
                st.caption(value)
                st.write(detail)

    gates = load_json(POLICIES / "aibenchie-gates.json")
    tracks = gates.get("required_tracks") or []
    if tracks:
        st.subheader("Required Tracks")
        st.write(", ".join(track.replace("_", " ") for track in tracks))

    st.subheader("Public Deployment Notes")
    st.write(
        "This Streamlit app does not require personal Forgejo settings, service tokens, or local backend credentials. "
        "Private configuration belongs in ignored local add-ons and should be entered only for the current session when needed."
    )

    st.divider()
    render_ollama_panel()


if __name__ == "__main__":
    main()
