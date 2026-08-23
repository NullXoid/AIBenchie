"""Compatibility entry point for the existing Streamlit Cloud deployment.

The public ``aibenchie.streamlit.app`` deployment was originally configured
to launch ``Benchmark.py``.  Keep that stable deployment target while routing
all rendering through the maintained application entry point.
"""

from streamlit_app import main


if __name__ == "__main__":
    main()
