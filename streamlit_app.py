from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import streamlit as st

from aibenchie.local_ollama import (
    DEFAULT_OLLAMA_URL,
    MAX_PROMPT_CHARS,
    MAX_PREDICT_TOKENS,
    benchmark_ollama_model,
    format_model_details,
    is_allowed_ollama_url,
    list_ollama_models,
    model_name,
)
from aibenchie.local_nullbridge_runner import find_repo_root, run_local_trust_path
from aibenchie.nullprivacy import run_e2ee_storage_proof
from aibenchie.release_report import build_release_report


ROOT = Path(__file__).resolve().parent
POLICIES = ROOT / ".suite" / "policies"
MASCOT = ROOT / "docs" / "assets" / "aibenchie-mascots.png"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def count_tests() -> int:
    total = 0
    for path in (ROOT / "tests").glob("test_*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        total += text.count("def test_")
    return total


def policy_status() -> list[tuple[str, str, str]]:
    gates = load_json(POLICIES / "aibenchie-gates.json")
    auth_policy = load_json(POLICIES / "auth-policy.json")
    resource = load_json(POLICIES / "resource-policy.json")
    privacy = load_json(POLICIES / "privacy-levels.json")
    release = load_json(POLICIES / "release-policy.json")
    setup = load_json(POLICIES / "setup-policy.json")
    source_hosts = load_json(POLICIES / "source-hosts.json")
    tracks = gates.get("required_tracks") or []
    providers = source_hosts.get("allowed_providers") or []
    setup_steps = setup.get("steps") or []
    return [
        ("Release gates", f"{len(tracks)} tracked", "Quality, platform, privacy, security, and release checks."),
        ("Guided setup", f"{len(setup_steps)} steps", "Standard setup must work from UI flows without a CLI requirement."),
        ("User auth", str(auth_policy.get("primary_user_auth", "unknown")).replace("_", " "), "Passkeys first, OIDC PKCE optional, no frontend service credentials."),
        ("Resource policy", "bounded" if resource.get("deny_unbounded_resources") else "review", "Heavy work requires capped leases."),
        ("Privacy levels", f"{len(privacy.get('levels', {}))} levels", "Local, secure remote, relay, and sovereign modes."),
        ("Source providers", f"{len(providers)} options", f"Recommended: {release.get('recommended_source_provider', 'not configured')}."),
    ]


def render_source_provider_panel() -> None:
    source_hosts = load_json(POLICIES / "source-hosts.json")
    providers = source_hosts.get("allowed_providers") or []
    by_label = {f"{item.get('label')} ({item.get('id')})": item for item in providers}
    default_id = source_hosts.get("default_provider", "forgejo")
    default_index = 0
    for index, item in enumerate(providers):
        if item.get("id") == default_id:
            default_index = index
            break

    st.subheader("Source Host")
    st.write(
        "Choose where this run should treat source, policy, manifests, and release evidence as coming from. "
        "AIBenchie does not store access tokens here; credentials should be entered only for the current session or supplied by an ignored local add-on."
    )
    if not by_label:
        st.warning("No source providers are configured.")
        return

    labels = list(by_label.keys())
    selected_label = st.selectbox("Provider", labels, index=default_index)
    selected = by_label[selected_label]
    col1, col2, col3 = st.columns(3)
    col1.metric("Provider", selected.get("label", "unknown"))
    col2.metric("Type", str(selected.get("kind", "unknown")).replace("_", " "))
    col3.metric("Credentials", str(selected.get("personal_config", "session_only")).replace("_", " "))
    st.caption(
        "Forgejo/Gitea are the recommended open-source self-hosted path. GitHub, GitLab, and custom Git remain supported so teams can adopt AIBenchie without changing hosts first."
    )


def render_setup_panel() -> None:
    setup = load_json(POLICIES / "setup-policy.json")
    auth_policy = load_json(POLICIES / "auth-policy.json")

    st.subheader("Guided Setup")
    st.write(
        "AIBenchie should guide normal users through source host, sign-in, backend, privacy, resources, "
        "route checks, and release gates without requiring terminal commands. Personal settings stay session-only "
        "or in ignored local add-ons."
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Setup mode", str(setup.get("setup_mode", "unknown")).replace("_", " "))
    col2.metric("CLI required", "no" if setup.get("cli_required_for_standard_setup") is False else "review")
    col3.metric("Primary sign-in", str(auth_policy.get("primary_user_auth", "unknown")).replace("_", " "))

    methods = [method.replace("_", " ") for method in auth_policy.get("allowed_user_auth_methods", [])]
    if methods:
        st.caption("Allowed sign-in methods: " + ", ".join(methods))

    steps = setup.get("steps") or []
    if steps:
        st.dataframe(
            [
                {
                    "step": item.get("label", item.get("id", "unknown")),
                    "cli": "no" if not item.get("requires_cli") else "required",
                    "secret saved": "no" if not item.get("stores_secret") else "yes",
                    "purpose": item.get("description", ""),
                }
                for item in steps
            ],
            use_container_width=True,
            hide_index=True,
        )


def render_release_verdict_panel() -> None:
    st.subheader("Release Verdict")
    st.write(
        "Generates a public-safe release summary plus an encrypted full report. The generated key is local-only and should be replaced with a device or hardware-key flow for production."
    )
    run_trust = st.checkbox("Include local NullBridge trust smoke", value=False)
    if st.button("Generate release verdict"):
        with st.spinner("Running release verdict checks..."):
            try:
                summary, encrypted, _key = build_release_report(ROOT, run_trust_smoke=run_trust)
            except Exception as exc:
                st.error(f"Release verdict failed: {exc}")
                return

        if summary["verdict"] == "ship_candidate":
            st.success("Release verdict: ship_candidate")
        else:
            st.error(f"Release verdict: {summary['verdict']}")

        col1, col2, col3 = st.columns(3)
        col1.metric("Source commit", summary["source_commit"][:12])
        col2.metric("Critical blocks", len(summary["critical_blocks"]))
        col3.metric("Encrypted report", "ready" if encrypted.get("ciphertext") else "missing")

        with st.expander("Track summary", expanded=True):
            st.dataframe(
                [{"track": track.replace("_", " "), "status": status} for track, status in summary["tracks"].items()],
                use_container_width=True,
            )
        with st.expander("Public-safe summary JSON", expanded=False):
            st.json(summary)


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

    model_names = [model_name(item) for item in models if model_name(item)]
    selected = st.selectbox("Detected models", model_names)

    with st.expander("Detected model details", expanded=False):
        st.dataframe(format_model_details(models), use_container_width=True)

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


def render_trust_fabric_panel() -> None:
    st.subheader("Trust Fabric Smoke Test")
    st.write(
        "Runs a local NullBridge instance with temporary generated service secrets, proves one allowed route "
        "and one denied route, then tears the instance down. No personal Forgejo settings or service secrets are saved."
    )

    repo = find_repo_root()
    if repo is None:
        st.warning("NullBridge repo was not found. Set AIBENCHIE_NULLBRIDGE_REPO before launching Streamlit.")
        return

    st.caption("NullBridge repo detected for this local session.")
    if st.button("Run trust smoke test"):
        with st.spinner("Starting temporary NullBridge and checking route policy..."):
            try:
                result = run_local_trust_path()
            except Exception as exc:
                st.error(f"Trust smoke test failed to run: {exc}")
                return

        if result.get("ok"):
            st.success("Trust fabric smoke test passed.")
        else:
            st.error("Trust fabric smoke test failed.")

        col1, col2, col3 = st.columns(3)
        col1.metric("Allowed route", f"HTTP {result['allow']['status']}")
        col2.metric("Denied route", f"HTTP {result['deny']['status']}")
        col3.metric("Secrets persisted", str(result["secrets_persisted"]).lower())

        with st.expander("Route proof", expanded=False):
            safe_result = {
                "allow": {
                    "status": result["allow"]["status"],
                    "accepted": result["allow"]["body"].get("accepted"),
                    "caller": result["allow"]["body"].get("caller"),
                    "capability": result["allow"]["body"].get("capability"),
                },
                "deny": {
                    "status": result["deny"]["status"],
                    "errorCode": result["deny"]["body"].get("errorCode"),
                    "reason": result["deny"]["body"].get("reason"),
                },
                "secrets_persisted": result["secrets_persisted"],
            }
            st.json(safe_result)


def render_privacy_panel() -> None:
    st.subheader("NullPrivacy Foundation")
    st.write(
        "Runs a local E2EE storage proof with temporary generated keys. The proof verifies that encrypted blobs "
        "round-trip with the right key, reject the wrong key, reject tampering, and do not contain plaintext."
    )

    if st.button("Run E2EE storage proof"):
        result = run_e2ee_storage_proof().as_dict()
        if result["ok"]:
            st.success("E2EE storage proof passed.")
        else:
            st.error("E2EE storage proof failed.")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Roundtrip", str(result["roundtrip_ok"]).lower())
        col2.metric("Wrong key", "rejected" if result["wrong_key_rejected"] else "accepted")
        col3.metric("Tamper", "rejected" if result["tamper_rejected"] else "accepted")
        col4.metric("Plaintext visible", str(result["plaintext_visible_in_blob"]).lower())


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
    render_setup_panel()

    st.divider()
    render_source_provider_panel()

    st.divider()
    render_release_verdict_panel()

    st.divider()
    render_trust_fabric_panel()

    st.divider()
    render_privacy_panel()

    st.divider()
    render_ollama_panel()


if __name__ == "__main__":
    main()
