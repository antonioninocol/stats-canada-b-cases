"""Streamlit entry point: renders the self-contained story page (story/story_en.html)."""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="How much does a degree protect in Canada?",
    page_icon="📊",
    layout="centered",
)

# Remove default Streamlit padding so the page fills the frame.
st.markdown(
    "<style>.block-container{padding-top:1rem;padding-bottom:1rem;max-width:980px}</style>",
    unsafe_allow_html=True,
)

HTML = Path(__file__).resolve().parent.parent / "story" / "story_en.html"
components.html(HTML.read_text(encoding="utf-8"), height=4300, scrolling=True)

st.caption(
    "Data: Statistics Canada tables 14-10-0287, 14-10-0432, 14-10-0471, 14-10-0086 and 14-10-0019 "
    "(Statistics Canada Open Licence). Static snapshot taken on 30 October 2026."
)
