"""GDPR Consent Components."""

import streamlit as st
from datetime import datetime
from pathlib import Path
import shutil


def show_gdpr_consent() -> bool:
    """
    Display GDPR consent banner. Returns True if user consents.
    Must be shown before any file upload is enabled.
    """

    if st.session_state.get("gdpr_consent_given"):
        return True

    st.markdown("---")
    st.markdown("## Data Privacy Notice")

    with st.expander("Read Full Privacy Policy", expanded=False):
        st.markdown("""
        ### How Your Data Is Handled

        **Processing Location:** Streamlit Cloud / Local Server

        **What We Process:**
        - The file(s) you upload for analysis
        - Configuration choices you make during the pipeline

        **What We Do NOT Do:**
        - Store your data beyond your browser session
        - Share your data with third parties
        - Use your data for training or analytics
        - Log or retain any uploaded file contents

        **Data Retention:**
        - All uploaded data exists only in temporary memory
        - Data is automatically deleted when you close the browser tab
        - No backups or copies are retained

        **Your Rights (GDPR Article 15-22):**
        - **Access:** Your data is visible to you throughout the session
        - **Rectification:** You control all data modifications via the pipeline
        - **Erasure:** Close the browser tab to immediately delete all data
        - **Portability:** Export your processed data at any time

        **Security Measures:**
        - All connections use HTTPS encryption
        - No data persistence beyond session memory
        - No third-party analytics or tracking

        **Legal Basis:** Consent (GDPR Article 6(1)(a))
        """)

    st.markdown("""
    **Summary:** Your uploaded data is processed in-memory only and
    automatically deleted when your session ends. No data is stored,
    shared, or retained.
    """)

    col1, col2 = st.columns([1, 4])

    with col1:
        consent = st.checkbox("I understand and consent")

    with col2:
        if consent:
            if st.button("Continue to Application", type="primary"):
                st.session_state.gdpr_consent_given = True
                st.session_state.consent_timestamp = datetime.utcnow().isoformat()
                st.rerun()

    if not consent:
        st.info("Please review and accept the privacy notice to continue.")

    return False


def show_privacy_footer():
    """Persistent footer with privacy controls."""

    st.markdown("---")
    cols = st.columns([2, 1, 1])

    with cols[0]:
        st.caption("Your data is processed in-memory only and not stored.")

    with cols[1]:
        if st.button("Delete All Data", key="footer_delete"):
            clear_all_session_data()
            st.success("All data cleared.")
            st.rerun()

    with cols[2]:
        if st.button("Privacy Policy", key="footer_privacy"):
            st.session_state.show_privacy_modal = True
            st.rerun()

    # Show privacy modal if requested
    if st.session_state.get("show_privacy_modal"):
        show_privacy_modal()


def show_privacy_modal():
    """Display privacy policy in a modal-like expander."""
    with st.expander("Privacy Policy", expanded=True):
        st.markdown("""
        ### How Your Data Is Handled

        **What We Process:**
        - The file(s) you upload for analysis
        - Configuration choices you make during the pipeline

        **What We Do NOT Do:**
        - Store your data beyond your browser session
        - Share your data with third parties
        - Use your data for training or analytics

        **Data Retention:**
        - All uploaded data exists only in temporary memory
        - Data is automatically deleted when you close the browser tab

        **Your Rights:**
        - **Access:** Your data is visible to you throughout the session
        - **Erasure:** Use "Delete All Data" button or close browser tab
        - **Portability:** Export your processed data at any time
        """)

        if st.button("Close", key="close_privacy_modal"):
            st.session_state.show_privacy_modal = False
            st.rerun()


def clear_all_session_data():
    """Explicitly clear all user data from session."""

    # Clear all dataframe states
    keys_to_clear = [
        k for k in list(st.session_state.keys())
        if k.startswith("df_") or k.startswith("pipeline_") or k.startswith("state_")
    ]

    for key in keys_to_clear:
        del st.session_state[key]

    # Clear state manager if exists
    if "state_manager" in st.session_state:
        st.session_state.state_manager.cleanup()
        del st.session_state["state_manager"]

    # Reset other session state
    keys_to_reset = ["current_phase", "uploaded_file", "config"]
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]

    # Clear temp files
    temp_dir = Path("/tmp/pipeline_states")
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(exist_ok=True)
