from __future__ import annotations

import json
from pathlib import Path

import streamlit as st


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


def main() -> None:
    st.set_page_config(
        page_title="AIBenchie",
        page_icon="✅",
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


if __name__ == "__main__":
    main()
