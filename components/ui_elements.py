"""UI Elements for each pipeline phase."""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional


def show_schema_editor(schema: Dict[str, Dict], df: pd.DataFrame) -> Dict[str, str]:
    """
    Display schema editor for type overrides.

    Returns:
        Dict of column -> target type overrides
    """
    st.markdown("### Schema Editor")
    st.caption("Review detected types and override if needed.")

    overrides = {}

    type_options = [
        "Keep Original", "string", "category", "int64", "float64",
        "datetime64[ns]", "boolean"
    ]

    # Create columns for layout
    for col_name, col_info in schema.items():
        col1, col2, col3, col4 = st.columns([3, 2, 2, 3])

        with col1:
            st.text(col_name)

        with col2:
            st.text(col_info["original_dtype"])

        with col3:
            override = st.selectbox(
                "Override",
                type_options,
                index=0,
                key=f"schema_{col_name}",
                label_visibility="collapsed"
            )
            if override != "Keep Original":
                overrides[col_name] = override

        with col4:
            samples = col_info.get("sample_values", [])[:3]
            st.text(", ".join(str(s) for s in samples))

    return overrides


def show_duplicate_resolver(dup_stats: Dict[str, Any], df: pd.DataFrame) -> Dict[str, Any]:
    """
    Display duplicate resolution interface.

    Returns:
        Dict with resolution configuration
    """
    st.markdown("### Duplicate Detection")

    config = {}

    # Exact duplicates
    st.markdown("#### Exact Duplicates")
    st.metric("Total Duplicates", dup_stats.get("total_duplicates", 0))
    st.metric("Rows to Remove", dup_stats.get("rows_to_remove", 0))

    if dup_stats.get("sample_groups"):
        with st.expander("Preview Duplicate Groups"):
            for group in dup_stats["sample_groups"][:3]:
                st.json(group)

    config["exact_resolution"] = st.selectbox(
        "Resolution Strategy",
        ["keep_first", "keep_last", "drop_all"],
        index=0,
        key="exact_dup_strategy"
    )

    # Subset duplicates
    st.markdown("#### Subset Duplicates")
    st.caption("Select key columns to identify duplicates.")

    key_columns = st.multiselect(
        "Key Columns",
        df.columns.tolist(),
        key="subset_key_cols"
    )

    config["subset_keys"] = key_columns

    if key_columns:
        config["subset_resolution"] = st.selectbox(
            "Subset Resolution",
            ["keep_first", "keep_last", "drop_all"],
            index=0,
            key="subset_dup_strategy"
        )

    return config


def show_column_selector(recommendations: Dict[str, Dict], df: pd.DataFrame) -> List[str]:
    """
    Display column selector with recommendations.

    Returns:
        List of selected column names
    """
    st.markdown("### Column Selection")

    # Auto-selection options
    auto_drop_zero = st.checkbox("Auto-drop zero variance columns", value=True)
    auto_drop_id = st.checkbox("Auto-drop high cardinality (ID) columns", value=False)

    st.markdown("#### Select Columns")

    selected = []

    for col_name, col_info in recommendations.items():
        flags = col_info.get("flags", [])
        flag_text = ""
        if flags:
            flag_text = f" - {flags[0]['message']}"

        default = col_info["recommendation"] != "drop"
        if auto_drop_zero and any(f["type"] == "zero_variance" for f in flags):
            default = False
        if auto_drop_id and any(f["type"] == "high_cardinality" for f in flags):
            default = False

        if st.checkbox(f"{col_name} ({col_info['dtype']}){flag_text}", value=default, key=f"col_{col_name}"):
            selected.append(col_name)

    st.caption(f"Selected: {len(selected)} of {len(recommendations)} columns")

    return selected


def show_constraint_editor(df: pd.DataFrame) -> Dict[str, str]:
    """
    Display constraint definition interface.

    Returns:
        Dict mapping column names to constraint expressions
    """
    st.markdown("### Define Constraints")
    st.caption("Define validation rules for your data.")

    constraints = {}

    # Predefined constraint templates
    st.markdown("#### Quick Add")
    col1, col2, col3 = st.columns(3)

    with col1:
        col = st.selectbox("Column", [""] + list(df.columns), key="constraint_col")
    with col2:
        op = st.selectbox("Operator", [">", ">=", "<", "<=", "==", "!=", "IN"], key="constraint_op")
    with col3:
        val = st.text_input("Value", key="constraint_val")

    if col and val:
        if op == "IN":
            constraint = f"{col} IN ({val})"
        else:
            constraint = f"{col} {op} {val}"
        st.code(constraint)

        if st.button("Add Constraint", key="add_constraint"):
            st.session_state.setdefault("constraints", {})[col] = constraint

    # Display current constraints
    if "constraints" in st.session_state and st.session_state.constraints:
        st.markdown("#### Current Constraints")
        for col, constraint in st.session_state.constraints.items():
            st.text(f"{col}: {constraint}")
        constraints = st.session_state.constraints.copy()

    return constraints


def show_missing_value_handler(missing_summary: Dict[str, Any]) -> Dict[str, Dict]:
    """
    Display missing value handling interface.

    Returns:
        Dict mapping columns to imputation strategies
    """
    st.markdown("### Missing Value Handling")

    strategies = {}

    columns = missing_summary.get("columns", [])
    if not columns:
        st.success("No missing values found!")
        return strategies

    st.metric("Total Missing Cells", missing_summary.get("total_missing_cells", 0))
    st.metric("Overall Missing %", f"{missing_summary.get('overall_missing_pct', 0):.2f}%")

    st.markdown("#### Configure Strategies")

    for col_info in columns:
        col_name = col_info["column"]
        missing_pct = col_info["missing_pct"]
        suggested = col_info.get("suggested_strategy", "drop")

        col1, col2, col3 = st.columns([3, 2, 3])

        with col1:
            st.text(f"{col_name} ({missing_pct:.1f}% missing)")

        with col2:
            method = st.selectbox(
                "Strategy",
                ["drop", "mean", "median", "mode", "constant", "unknown_tag"],
                index=["drop", "mean", "median", "mode", "constant", "unknown_tag"].index(suggested),
                key=f"impute_{col_name}",
                label_visibility="collapsed"
            )

        with col3:
            if method in ["constant", "unknown_tag"]:
                value = st.text_input(
                    "Value",
                    value="Unknown" if method == "unknown_tag" else "0",
                    key=f"impute_val_{col_name}",
                    label_visibility="collapsed"
                )
                strategies[col_name] = {"method": method, "value": value}
            else:
                strategies[col_name] = {"method": method}

    return strategies


def show_outlier_handler(outlier_summary: Dict[str, Any]) -> Dict[str, Dict]:
    """
    Display outlier handling interface.

    Returns:
        Dict mapping columns to resolution strategies
    """
    st.markdown("### Outlier Handling")

    # Method selection
    col1, col2 = st.columns(2)
    with col1:
        method = st.selectbox(
            "Detection Method",
            ["iqr", "zscore", "modified_zscore"],
            key="outlier_method"
        )
    with col2:
        if method == "iqr":
            threshold = st.slider("IQR Multiplier", 1.0, 3.0, 1.5, key="outlier_threshold")
        else:
            threshold = st.slider("Z-Score Threshold", 2.0, 4.0, 3.0, key="outlier_threshold")

    resolutions = {}

    column_summaries = outlier_summary.get("column_summaries", [])

    if not column_summaries:
        st.success("No outliers detected with current settings.")
        return resolutions

    st.markdown("#### Columns with Outliers")

    for col_summary in column_summaries:
        col_name = col_summary["column"]
        outlier_count = col_summary["outlier_count"]
        outlier_pct = col_summary["outlier_pct"]

        col1, col2, col3 = st.columns([3, 2, 3])

        with col1:
            st.text(f"{col_name}")
            st.caption(f"{outlier_count} outliers ({outlier_pct:.1f}%)")

        with col2:
            action = st.selectbox(
                "Action",
                ["keep", "drop", "winsorize"],
                key=f"outlier_{col_name}",
                label_visibility="collapsed"
            )

        with col3:
            if action == "winsorize":
                lower = st.number_input("Lower %", 1, 10, 1, key=f"win_lower_{col_name}")
                upper = st.number_input("Upper %", 90, 99, 99, key=f"win_upper_{col_name}")
                resolutions[col_name] = {"action": action, "lower_pct": lower, "upper_pct": upper}
            else:
                resolutions[col_name] = {"action": action}

    return resolutions


def show_multicollinearity_handler(mc_result: Dict[str, Any]) -> Dict[str, str]:
    """
    Display multicollinearity resolution interface.

    Returns:
        Dict mapping columns to actions
    """
    st.markdown("### Multicollinearity Analysis")

    # Threshold settings
    col1, col2 = st.columns(2)
    with col1:
        corr_threshold = st.slider("Correlation Threshold", 0.7, 0.99, 0.9, key="corr_thresh")
    with col2:
        vif_threshold = st.slider("VIF Threshold", 5, 20, 10, key="vif_thresh")

    actions = {}

    # High correlations
    high_corr = mc_result.get("high_correlation_pairs", [])
    if high_corr:
        st.markdown("#### Highly Correlated Pairs")
        for pair in high_corr[:10]:
            st.text(f"{pair['column1']} <-> {pair['column2']}: {pair['correlation']:.3f}")

    # High VIF
    high_vif = mc_result.get("high_vif_columns", [])
    if high_vif:
        st.markdown("#### High VIF Columns")
        for col in high_vif:
            col1, col2 = st.columns([3, 2])
            with col1:
                st.text(f"{col['column']} (VIF: {col['vif']:.1f})")
            with col2:
                action = st.selectbox(
                    "Action",
                    ["keep", "drop", "flag"],
                    key=f"mc_{col['column']}",
                    label_visibility="collapsed"
                )
                actions[col["column"]] = action

    # Recommendations
    recommendations = mc_result.get("recommendations", [])
    if recommendations:
        st.markdown("#### Recommendations")
        for rec in recommendations:
            st.info(f"Consider {rec['action']}ing `{rec['column']}`: {rec['reason']}")

    return actions


def show_encoding_selector(categorical_info: Dict[str, Any]) -> Dict[str, Dict]:
    """
    Display encoding configuration interface.

    Returns:
        Dict mapping columns to encoding config
    """
    st.markdown("### Categorical Encoding")

    encoding_config = {}

    columns = categorical_info.get("columns", [])

    if not columns:
        st.info("No categorical columns detected.")
        return encoding_config

    for col_info in columns:
        col_name = col_info["column"]
        unique_count = col_info["unique_count"]
        suggested = col_info.get("suggested_encoding", "one_hot")

        col1, col2, col3 = st.columns([3, 2, 3])

        with col1:
            st.text(f"{col_name}")
            st.caption(f"{unique_count} unique values")

        with col2:
            method = st.selectbox(
                "Encoding",
                ["one_hot", "label", "skip"],
                index=["one_hot", "label", "skip"].index(suggested) if suggested in ["one_hot", "label"] else 0,
                key=f"encode_{col_name}",
                label_visibility="collapsed"
            )

        with col3:
            samples = col_info.get("sample_values", [])[:3]
            st.caption(", ".join(str(s) for s in samples))

        if method != "skip":
            encoding_config[col_name] = {"method": method}

    # Scaling options
    st.markdown("### Scaling")
    apply_scaling = st.checkbox("Apply Scaling", value=False)

    if apply_scaling:
        scaling_method = st.selectbox(
            "Scaling Method",
            ["standard", "minmax", "robust"]
        )
        encoding_config["_scaling"] = {"method": scaling_method}

    return encoding_config


def show_state_timeline(sm) -> Optional[str]:
    """
    Display pipeline state timeline.

    Returns:
        Selected state ID if rollback requested
    """
    st.markdown("### Pipeline States")

    states = sm.get_state_history()
    current_id = sm.get_current_state_id()

    if not states:
        st.info("No states saved yet.")
        return None

    rollback_target = None

    for state in states:
        is_current = state.id == current_id
        status_icon = "" if is_current else ""

        with st.container():
            col1, col2 = st.columns([4, 1])

            with col1:
                label = f"{status_icon} {state.id}"
                st.markdown(f"**{label}**")
                st.caption(f"{state.delta_summary}")
                st.caption(f"{state.row_count:,} rows x {state.col_count} cols")

            with col2:
                if not is_current:
                    if st.button("Rollback", key=f"rollback_{state.id}"):
                        rollback_target = state.id

            st.divider()

    return rollback_target
