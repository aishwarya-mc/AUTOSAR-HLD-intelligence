import streamlit as st

st.set_page_config(
    page_title="AUTOSAR HLD Intelligence",
    page_icon="??",
    layout="wide",
)

st.title("AUTOSAR HLD Intelligence & Traceability Platform")

st.markdown(
    """
    ### Evidence-Grounded Architecture Analysis

    Analyze AUTOSAR High-Level Design documents and extract:

    - Architecture components
    - Interfaces
    - Ports
    - Signals
    - Dependencies
    - Functional flows
    - Validation findings
    - Revision changes
    - Evidence-backed answers

    > AI-generated findings remain subject to human engineering review.
    """
)

st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Documents", "0")

with col2:
    st.metric("Architecture Entities", "0")

with col3:
    st.metric("Validation Findings", "0")

st.info(
    "Upload an approved AUTOSAR HLD document from the Documents page "
    "to begin analysis."
)
