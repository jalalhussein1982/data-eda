"""
Data Preparation Pipeline - Main Application

A comprehensive, GDPR-compliant data preparation tool for cleaning, validating,
and transforming datasets before correlation analysis.
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

# Pipeline modules
from pipeline.state_manager import StateManager
from pipeline.ingestion import ingest_file, detect_schema, apply_schema_overrides, get_initial_profile
from pipeline.duplicates import detect_exact_duplicates, detect_subset_duplicates, resolve_duplicates
from pipeline.scope import get_column_recommendations, apply_scope_selection
from pipeline.cleaning import validate_constraints, get_missing_summary, impute_missing_values, apply_constraint_resolution
from pipeline.outliers import detect_outliers, resolve_outliers, get_outlier_summary
from pipeline.multicollinearity import detect_multicollinearity, resolve_multicollinearity
from pipeline.encoding import encode_categorical, apply_scaling, detect_categorical_columns

# Components
from components.gdpr_consent import show_gdpr_consent, show_privacy_footer, clear_all_session_data
from components.distribution_inspector import show_distribution_inspector
from components.ui_elements import (
    show_schema_editor, show_duplicate_resolver, show_column_selector,
    show_constraint_editor, show_missing_value_handler, show_outlier_handler,
    show_multicollinearity_handler, show_encoding_selector, show_state_timeline
)

# Utilities
from utils.export import export_dataframe, export_report, get_file_extension, get_mime_type
from utils.visualization import create_correlation_heatmap, create_missing_heatmap

# Page configuration
st.set_page_config(
    page_title="Data Preparation Pipeline",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Pipeline phases
PHASES = [
    ("upload", "Upload Data"),
    ("schema", "Schema Enforcement"),
    ("duplicates", "Duplicate Detection"),
    ("scope", "Column Selection"),
    ("cleaning", "Data Cleaning"),
    ("outliers", "Outlier Handling"),
    ("multicollinearity", "Multicollinearity"),
    ("encoding", "Encoding & Scaling"),
    ("export", "Export")
]


def init_session_state():
    """Initialize session state variables."""
    if "state_manager" not in st.session_state:
        st.session_state.state_manager = StateManager()
    if "current_phase" not in st.session_state:
        st.session_state.current_phase = "upload"
    if "config" not in st.session_state:
        st.session_state.config = {}


def show_sidebar():
    """Display sidebar with phase navigation and state timeline."""
    with st.sidebar:
        st.markdown("## Pipeline Progress")

        # Phase navigation
        current_idx = next((i for i, (p, _) in enumerate(PHASES) if p == st.session_state.current_phase), 0)

        for i, (phase_id, phase_name) in enumerate(PHASES):
            if i < current_idx:
                st.markdown(f" {phase_name}")
            elif i == current_idx:
                st.markdown(f"**{phase_name}**")
            else:
                st.markdown(f" {phase_name}")

        st.divider()

        # Distribution Inspector button
        if st.button("Distribution Inspector", use_container_width=True):
            st.session_state.show_inspector = not st.session_state.get("show_inspector", False)

        # State timeline
        if st.session_state.state_manager.get_state_history():
            st.divider()
            rollback_target = show_state_timeline(st.session_state.state_manager)
            if rollback_target:
                st.session_state.state_manager.create_branch(
                    f"branch_{len(st.session_state.state_manager.branches)}",
                    rollback_target
                )
                st.success(f"Rolled back to {rollback_target}")
                st.rerun()


def phase_upload():
    """Phase: File Upload."""
    st.header("Upload Your Data")

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["csv", "xlsx", "xls", "parquet", "json"],
        help="Supported formats: CSV, Excel, Parquet, JSON"
    )

    if uploaded_file:
        with st.spinner("Loading file..."):
            try:
                df, metadata = ingest_file(
                    uploaded_file.read(),
                    uploaded_file.name
                )

                # Show preview
                st.markdown("### Data Preview")
                st.dataframe(df.head(10), use_container_width=True)

                # Show profile
                profile = get_initial_profile(df)
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Rows", f"{profile['row_count']:,}")
                with col2:
                    st.metric("Columns", profile['col_count'])
                with col3:
                    st.metric("Memory", f"{profile['memory_usage_mb']:.2f} MB")
                with col4:
                    st.metric("Types", len(profile['type_distribution']))

                # Proceed button
                if st.button("Continue to Schema Enforcement", type="primary"):
                    # Save raw state
                    st.session_state.state_manager.commit_state(
                        "df_raw",
                        df,
                        {"source": metadata},
                        f"Loaded {uploaded_file.name}"
                    )
                    st.session_state.current_phase = "schema"
                    st.rerun()

            except Exception as e:
                st.error(f"Error loading file: {str(e)}")


def phase_schema():
    """Phase I: Schema Enforcement."""
    st.header("Schema Enforcement")

    df = st.session_state.state_manager.get_current_state()
    if df is None:
        st.warning("No data loaded. Please upload a file first.")
        return

    # Detect schema
    schema = detect_schema(df)

    # Show schema editor
    overrides = show_schema_editor(schema, df)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Apply Schema & Continue", type="primary"):
            if overrides:
                df, errors = apply_schema_overrides(df, overrides)
                if errors:
                    for err in errors:
                        st.warning(err)

            st.session_state.state_manager.commit_state(
                "df_schema",
                df,
                {"type_overrides": overrides},
                f"Applied {len(overrides)} type overrides" if overrides else "Schema validated"
            )
            st.session_state.current_phase = "duplicates"
            st.rerun()

    with col2:
        if st.button("Skip (Keep Original Types)"):
            st.session_state.state_manager.commit_state(
                "df_schema",
                df,
                {},
                "Schema kept as original"
            )
            st.session_state.current_phase = "duplicates"
            st.rerun()


def phase_duplicates():
    """Phase I-A: Duplicate Detection."""
    st.header("Duplicate Detection")

    df = st.session_state.state_manager.get_current_state()
    if df is None:
        st.warning("No data available.")
        return

    # Detect duplicates
    dup_stats = detect_exact_duplicates(df)

    # Show resolver
    config = show_duplicate_resolver(dup_stats, df)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Resolve Duplicates & Continue", type="primary"):
            # Resolve exact duplicates
            df_clean, stats = resolve_duplicates(
                df,
                strategy=config.get("exact_resolution", "keep_first")
            )

            # Resolve subset duplicates if configured
            if config.get("subset_keys"):
                df_clean, subset_stats = resolve_duplicates(
                    df_clean,
                    strategy=config.get("subset_resolution", "keep_first"),
                    subset=config["subset_keys"]
                )

            st.session_state.state_manager.commit_state(
                "df_deduplicated",
                df_clean,
                config,
                f"Removed {len(df) - len(df_clean)} duplicate rows"
            )
            st.session_state.current_phase = "scope"
            st.rerun()

    with col2:
        if st.button("Skip (Keep All Rows)"):
            st.session_state.state_manager.commit_state(
                "df_deduplicated",
                df,
                {},
                "No duplicates removed"
            )
            st.session_state.current_phase = "scope"
            st.rerun()


def phase_scope():
    """Phase II: Scope Definition."""
    st.header("Column Selection")

    df = st.session_state.state_manager.get_current_state()
    if df is None:
        st.warning("No data available.")
        return

    # Get recommendations
    recommendations = get_column_recommendations(df)

    # Show selector
    selected = show_column_selector(recommendations, df)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Apply Selection & Continue", type="primary"):
            df_scoped, stats = apply_scope_selection(df, selected)

            st.session_state.state_manager.commit_state(
                "df_scoped",
                df_scoped,
                {"selected_columns": selected},
                f"Selected {len(selected)} of {len(df.columns)} columns"
            )
            st.session_state.current_phase = "cleaning"
            st.rerun()

    with col2:
        if st.button("Skip (Keep All Columns)"):
            st.session_state.state_manager.commit_state(
                "df_scoped",
                df,
                {"selected_columns": list(df.columns)},
                "All columns kept"
            )
            st.session_state.current_phase = "cleaning"
            st.rerun()


def phase_cleaning():
    """Phase III: Data Cleaning."""
    st.header("Data Cleaning")

    df = st.session_state.state_manager.get_current_state()
    if df is None:
        st.warning("No data available.")
        return

    tab1, tab2 = st.tabs(["Missing Values", "Constraints"])

    with tab1:
        # Missing value summary
        missing_summary = get_missing_summary(df)

        # Show handler
        imputation_strategies = show_missing_value_handler(missing_summary)

    with tab2:
        # Constraint editor
        constraints = show_constraint_editor(df)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Apply Cleaning & Continue", type="primary"):
            df_clean = df.copy()

            # Apply constraints
            if constraints:
                actions = {col: "convert_nan" for col in constraints}
                df_clean, constraint_stats = apply_constraint_resolution(df_clean, constraints, actions)

            # Apply imputation
            if imputation_strategies:
                df_clean, imputation_stats = impute_missing_values(df_clean, imputation_strategies)

            st.session_state.state_manager.commit_state(
                "df_clean",
                df_clean,
                {"constraints": constraints, "imputation": imputation_strategies},
                f"Cleaned data: {len(df_clean)} rows"
            )
            st.session_state.current_phase = "outliers"
            st.rerun()

    with col2:
        if st.button("Skip Cleaning"):
            st.session_state.state_manager.commit_state(
                "df_clean",
                df,
                {},
                "No cleaning applied"
            )
            st.session_state.current_phase = "outliers"
            st.rerun()


def phase_outliers():
    """Phase IV: Outlier Handling."""
    st.header("Outlier Detection & Handling")

    df = st.session_state.state_manager.get_current_state()
    if df is None:
        st.warning("No data available.")
        return

    # Detection settings
    col1, col2 = st.columns(2)
    with col1:
        method = st.selectbox("Detection Method", ["iqr", "zscore", "modified_zscore"])
    with col2:
        if method == "iqr":
            threshold = st.slider("IQR Multiplier", 1.0, 3.0, 1.5)
        else:
            threshold = st.slider("Z-Score Threshold", 2.0, 4.0, 3.0)

    # Get summary
    outlier_summary = get_outlier_summary(df, method=method, threshold=threshold)

    # Show handler
    resolutions = show_outlier_handler(outlier_summary)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Apply Outlier Handling & Continue", type="primary"):
            df_handled, stats = resolve_outliers(
                df,
                resolutions,
                method=method,
                threshold=threshold
            )

            st.session_state.state_manager.commit_state(
                "df_outlier_handled",
                df_handled,
                {"method": method, "threshold": threshold, "resolutions": resolutions},
                f"Handled outliers: {len(df_handled)} rows"
            )
            st.session_state.current_phase = "multicollinearity"
            st.rerun()

    with col2:
        if st.button("Skip Outlier Handling"):
            st.session_state.state_manager.commit_state(
                "df_outlier_handled",
                df,
                {},
                "No outlier handling applied"
            )
            st.session_state.current_phase = "multicollinearity"
            st.rerun()


def phase_multicollinearity():
    """Phase IV-A: Multicollinearity Screening."""
    st.header("Multicollinearity Analysis")

    df = st.session_state.state_manager.get_current_state()
    if df is None:
        st.warning("No data available.")
        return

    # Check if enough numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if len(numeric_cols) < 2:
        st.info("Not enough numeric columns for multicollinearity analysis.")
        if st.button("Continue to Encoding", type="primary"):
            st.session_state.state_manager.commit_state(
                "df_collinear_resolved",
                df,
                {},
                "Skipped multicollinearity (insufficient numeric columns)"
            )
            st.session_state.current_phase = "encoding"
            st.rerun()
        return

    # Analysis settings
    col1, col2 = st.columns(2)
    with col1:
        corr_threshold = st.slider("Correlation Threshold", 0.7, 0.99, 0.9)
    with col2:
        vif_threshold = st.slider("VIF Threshold", 5, 20, 10)

    # Run analysis
    mc_result = detect_multicollinearity(
        df,
        correlation_threshold=corr_threshold,
        vif_threshold=vif_threshold
    )

    # Show correlation heatmap
    if len(numeric_cols) <= 20:
        st.markdown("### Correlation Matrix")
        fig = create_correlation_heatmap(df, numeric_cols)
        st.plotly_chart(fig, use_container_width=True)

    # Show handler
    actions = show_multicollinearity_handler(mc_result)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Apply & Continue", type="primary"):
            df_resolved, stats = resolve_multicollinearity(df, actions)

            st.session_state.state_manager.commit_state(
                "df_collinear_resolved",
                df_resolved,
                {"actions": actions},
                f"Resolved multicollinearity: {len(df_resolved.columns)} columns"
            )
            st.session_state.current_phase = "encoding"
            st.rerun()

    with col2:
        if st.button("Skip"):
            st.session_state.state_manager.commit_state(
                "df_collinear_resolved",
                df,
                {},
                "No multicollinearity resolution applied"
            )
            st.session_state.current_phase = "encoding"
            st.rerun()


def phase_encoding():
    """Phase V: Encoding & Scaling."""
    st.header("Encoding & Scaling")

    df = st.session_state.state_manager.get_current_state()
    if df is None:
        st.warning("No data available.")
        return

    # Detect categorical columns
    categorical_info = detect_categorical_columns(df)

    # Show encoding selector
    encoding_config = show_encoding_selector(categorical_info)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Apply Encoding & Finish", type="primary"):
            df_encoded = df.copy()

            # Apply categorical encoding
            cat_config = {k: v for k, v in encoding_config.items() if k != "_scaling"}
            if cat_config:
                df_encoded, encoding_stats = encode_categorical(df_encoded, cat_config)

            # Apply scaling
            if "_scaling" in encoding_config:
                df_encoded, scaling_stats = apply_scaling(
                    df_encoded,
                    {"method": encoding_config["_scaling"]["method"]}
                )

            st.session_state.state_manager.commit_state(
                "df_final",
                df_encoded,
                encoding_config,
                f"Final dataset: {len(df_encoded)} rows x {len(df_encoded.columns)} columns"
            )
            st.session_state.current_phase = "export"
            st.rerun()

    with col2:
        if st.button("Skip Encoding"):
            st.session_state.state_manager.commit_state(
                "df_final",
                df,
                {},
                "No encoding applied"
            )
            st.session_state.current_phase = "export"
            st.rerun()


def phase_export():
    """Phase: Export."""
    st.header("Export Your Data")

    df = st.session_state.state_manager.get_current_state()
    if df is None:
        st.warning("No data available.")
        return

    # Summary
    st.markdown("### Final Dataset Summary")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Rows", f"{len(df):,}")
    with col2:
        st.metric("Columns", len(df.columns))
    with col3:
        st.metric("Memory", f"{df.memory_usage(deep=True).sum() / 1e6:.2f} MB")

    # Preview
    st.markdown("### Data Preview")
    st.dataframe(df.head(10), use_container_width=True)

    # Export options
    st.markdown("### Export Options")

    col1, col2 = st.columns(2)

    with col1:
        export_format = st.selectbox(
            "Export Format",
            ["csv", "excel", "parquet", "json"]
        )

    with col2:
        filename = st.text_input(
            "Filename",
            value="processed_data"
        )

    # Export button
    if st.button("Download", type="primary"):
        try:
            data = export_dataframe(df, format=export_format)
            ext = get_file_extension(export_format)
            mime = get_mime_type(export_format)

            st.download_button(
                label=f"Click to Download {filename}{ext}",
                data=data,
                file_name=f"{filename}{ext}",
                mime=mime
            )
        except Exception as e:
            st.error(f"Export failed: {str(e)}")

    # Generate report
    st.markdown("### Pipeline Report")
    if st.button("Generate Report"):
        report = export_report(
            df,
            st.session_state.config,
            {}
        )
        st.download_button(
            label="Download Report (Markdown)",
            data=report,
            file_name="pipeline_report.md",
            mime="text/markdown"
        )

    # Start over
    st.divider()
    if st.button("Start New Pipeline"):
        clear_all_session_data()
        st.session_state.current_phase = "upload"
        st.rerun()


def main():
    """Main application entry point."""
    st.title("Data Preparation Pipeline")

    # GDPR gate - must consent before accessing app
    if not show_gdpr_consent():
        st.stop()

    # Initialize session
    init_session_state()

    # Show sidebar
    show_sidebar()

    # Distribution Inspector modal
    if st.session_state.get("show_inspector"):
        with st.expander("Distribution Inspector", expanded=True):
            show_distribution_inspector()
            if st.button("Close Inspector"):
                st.session_state.show_inspector = False
                st.rerun()
        st.divider()

    # Route to current phase
    phase_handlers = {
        "upload": phase_upload,
        "schema": phase_schema,
        "duplicates": phase_duplicates,
        "scope": phase_scope,
        "cleaning": phase_cleaning,
        "outliers": phase_outliers,
        "multicollinearity": phase_multicollinearity,
        "encoding": phase_encoding,
        "export": phase_export
    }

    handler = phase_handlers.get(st.session_state.current_phase, phase_upload)
    handler()

    # Persistent privacy footer
    show_privacy_footer()


if __name__ == "__main__":
    main()
