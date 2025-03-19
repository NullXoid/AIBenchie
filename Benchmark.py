# benchmark_web.py
# Description: Streamlit-based UI for running the local Ollama benchmark tool from the browser. Can be launched via Streamlit Cloud or locally.

import streamlit as st
from benchmark_router import list_models, benchmark_model
from smart_model_router import smart_model_router

st.set_page_config(page_title="🧪 Ollama Benchmark UI", layout="centered")
st.title("🧠 Ollama Benchmark v0.02 Web UI")

models = list_models()

if not models:
    st.error("No models found. Please make sure Ollama is running locally.")
    st.stop()

model = st.selectbox("Choose a model", models)
prompt = st.text_area("Prompt", "What causes a star to become a black hole?")
use_router = st.checkbox("Use smart_model_router", value=False)

if st.button("Run Benchmark"):
    with st.spinner("Running benchmark..."):
        benchmark_model(model, prompt, use_router=use_router, headless=True)
