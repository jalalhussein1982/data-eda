"""Distribution Inspector Component."""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from utils.visualization import (
    create_histogram,
    create_boxplot,
    create_distribution_comparison,
    create_small_multiples
)


def show_distribution_inspector():
    """Display the Distribution Inspector modal/panel."""

    st.markdown("## Distribution Inspector")

    if "state_manager" not in st.session_state:
        st.warning("No data loaded yet.")
        return

    sm = st.session_state.state_manager

    # Mode selection
    mode = st.radio(
        "Mode",
        ["Single Column", "Compare States", "Multi-Column Overview"],
        horizontal=True
    )

    if mode == "Single Column":
        show_single_column_view(sm)
    elif mode == "Compare States":
        show_compare_states_view(sm)
    else:
        show_multi_column_view(sm)


def show_single_column_view(sm):
    """Show single column distribution view."""
    current_df = sm.get_current_state()
    if current_df is None:
        st.warning("No data available.")
        return

    col1, col2 = st.columns([1, 1])

    with col1:
        column = st.selectbox(
            "Select Column",
            current_df.columns.tolist()
        )

    with col2:
        viz_type = st.selectbox(
            "Visualization",
            ["Histogram", "Boxplot", "Both"]
        )

    if column:
        col_data = current_df[column].dropna()

        if pd.api.types.is_numeric_dtype(col_data):
            # Show visualization options
            show_kde = st.checkbox("Show KDE", value=True)
            bins = st.slider("Bins", 10, 100, 30)

            if viz_type in ["Histogram", "Both"]:
                fig = create_histogram(current_df, column, bins=bins, show_kde=show_kde)
                st.plotly_chart(fig, use_container_width=True)

            if viz_type in ["Boxplot", "Both"]:
                fig = create_boxplot(current_df, column)
                st.plotly_chart(fig, use_container_width=True)

            # Statistics
            st.markdown("### Statistics")
            stats_col1, stats_col2 = st.columns(2)

            with stats_col1:
                st.metric("Mean", f"{col_data.mean():.4f}")
                st.metric("Median", f"{col_data.median():.4f}")
                st.metric("Std Dev", f"{col_data.std():.4f}")
                st.metric("Skewness", f"{col_data.skew():.4f}")

            with stats_col2:
                st.metric("Min", f"{col_data.min():.4f}")
                st.metric("Max", f"{col_data.max():.4f}")
                st.metric("Kurtosis", f"{col_data.kurtosis():.4f}")
                st.metric("Missing", f"{current_df[column].isna().sum()}")

            # Percentiles
            with st.expander("Percentiles"):
                percentiles = [1, 5, 25, 50, 75, 95, 99]
                perc_data = {f"{p}%": col_data.quantile(p/100) for p in percentiles}
                st.json(perc_data)

        else:
            # Categorical column
            st.markdown("### Value Counts")
            value_counts = current_df[column].value_counts()
            st.bar_chart(value_counts.head(20))

            st.markdown("### Summary")
            st.metric("Unique Values", current_df[column].nunique())
            st.metric("Mode", str(current_df[column].mode().iloc[0]) if len(current_df[column].mode()) > 0 else "N/A")
            st.metric("Missing", current_df[column].isna().sum())


def show_compare_states_view(sm):
    """Show comparison between two pipeline states."""
    states = sm.get_state_history()

    if len(states) < 2:
        st.info("Need at least 2 pipeline states to compare. Process more phases first.")
        return

    state_names = [s.id for s in states]

    col1, col2 = st.columns(2)
    with col1:
        state_a = st.selectbox("State A", state_names, index=0)
    with col2:
        state_b = st.selectbox("State B", state_names, index=len(state_names)-1)

    if state_a == state_b:
        st.warning("Select different states to compare.")
        return

    try:
        df_a = sm.load_state(sm.active_branch, state_a)
        df_b = sm.load_state(sm.active_branch, state_b)
    except:
        st.error("Could not load one or both states.")
        return

    # Find common numeric columns
    common_cols = list(set(df_a.columns) & set(df_b.columns))
    numeric_cols = [c for c in common_cols if pd.api.types.is_numeric_dtype(df_a[c])]

    if not numeric_cols:
        st.warning("No common numeric columns to compare.")
        return

    column = st.selectbox("Column to Compare", numeric_cols)

    if column:
        # Comparison visualization
        fig = create_distribution_comparison(df_a, df_b, column)
        st.plotly_chart(fig, use_container_width=True)

        # Statistics comparison
        st.markdown("### Statistical Comparison")

        def get_stats(df, col):
            data = df[col].dropna()
            return {
                "Mean": data.mean(),
                "Median": data.median(),
                "Std Dev": data.std(),
                "Min": data.min(),
                "Max": data.max(),
                "Skewness": data.skew(),
                "Kurtosis": data.kurtosis()
            }

        stats_a = get_stats(df_a, column)
        stats_b = get_stats(df_b, column)

        comparison_data = []
        for metric in stats_a.keys():
            val_a = stats_a[metric]
            val_b = stats_b[metric]
            if val_a != 0:
                change = ((val_b - val_a) / abs(val_a)) * 100
            else:
                change = 0

            comparison_data.append({
                "Metric": metric,
                state_a: f"{val_a:.4f}",
                state_b: f"{val_b:.4f}",
                "Change": f"{change:+.2f}%"
            })

        st.dataframe(pd.DataFrame(comparison_data), hide_index=True)


def show_multi_column_view(sm):
    """Show overview of all numeric columns."""
    current_df = sm.get_current_state()
    if current_df is None:
        st.warning("No data available.")
        return

    numeric_cols = current_df.select_dtypes(include=[np.number]).columns.tolist()

    if not numeric_cols:
        st.warning("No numeric columns available.")
        return

    st.markdown("### Distribution Overview")

    # Column filter
    show_type = st.radio("Show", ["Numeric Only", "All Columns"], horizontal=True)

    if show_type == "Numeric Only":
        cols_to_show = numeric_cols[:12]
    else:
        cols_to_show = current_df.columns.tolist()[:12]

    # Create small multiples
    fig = create_small_multiples(current_df, cols_to_show)
    st.plotly_chart(fig, use_container_width=True)

    # Summary table
    st.markdown("### Summary Statistics")

    summary_data = []
    for col in numeric_cols:
        data = current_df[col].dropna()
        summary_data.append({
            "Column": col,
            "Mean": f"{data.mean():.2f}",
            "Median": f"{data.median():.2f}",
            "Std": f"{data.std():.2f}",
            "Skewness": f"{data.skew():.2f}",
            "Missing": current_df[col].isna().sum()
        })

    st.dataframe(pd.DataFrame(summary_data), hide_index=True)
