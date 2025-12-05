"""Visualization utilities using Plotly."""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional, List, Dict, Any


def create_histogram(
    df: pd.DataFrame,
    column: str,
    bins: int = 30,
    show_kde: bool = True,
    title: Optional[str] = None
) -> go.Figure:
    """
    Create a histogram with optional KDE overlay.

    Args:
        df: Input DataFrame
        column: Column to plot
        bins: Number of bins
        show_kde: Whether to show KDE overlay
        title: Optional title

    Returns:
        Plotly figure
    """
    data = df[column].dropna()

    fig = go.Figure()

    # Add histogram
    fig.add_trace(go.Histogram(
        x=data,
        nbinsx=bins,
        name="Histogram",
        opacity=0.7,
        marker_color="#4F8BF9"
    ))

    if show_kde and len(data) > 10:
        # Add KDE
        from scipy import stats
        kde = stats.gaussian_kde(data)
        x_range = np.linspace(data.min(), data.max(), 100)
        kde_values = kde(x_range)

        # Scale KDE to match histogram
        hist_counts, _ = np.histogram(data, bins=bins)
        scale = hist_counts.max() / kde_values.max() if kde_values.max() > 0 else 1

        fig.add_trace(go.Scatter(
            x=x_range,
            y=kde_values * scale,
            mode="lines",
            name="KDE",
            line=dict(color="red", width=2)
        ))

    fig.update_layout(
        title=title or f"Distribution of {column}",
        xaxis_title=column,
        yaxis_title="Count",
        showlegend=True,
        template="plotly_white"
    )

    return fig


def create_boxplot(
    df: pd.DataFrame,
    column: str,
    show_points: bool = True,
    title: Optional[str] = None
) -> go.Figure:
    """
    Create a boxplot.

    Args:
        df: Input DataFrame
        column: Column to plot
        show_points: Whether to show individual points
        title: Optional title

    Returns:
        Plotly figure
    """
    data = df[column].dropna()

    fig = go.Figure()

    fig.add_trace(go.Box(
        y=data,
        name=column,
        boxpoints="outliers" if not show_points else "all",
        jitter=0.3,
        pointpos=-1.8,
        marker_color="#4F8BF9"
    ))

    fig.update_layout(
        title=title or f"Boxplot of {column}",
        yaxis_title=column,
        template="plotly_white"
    )

    return fig


def create_correlation_heatmap(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    threshold: float = 0.0,
    title: Optional[str] = None
) -> go.Figure:
    """
    Create a correlation heatmap.

    Args:
        df: Input DataFrame
        columns: Columns to include (None = all numeric)
        threshold: Only show correlations above this threshold
        title: Optional title

    Returns:
        Plotly figure
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    columns = [c for c in columns if c in df.columns][:20]  # Limit for readability

    corr_matrix = df[columns].corr()

    # Apply threshold mask
    if threshold > 0:
        mask = np.abs(corr_matrix) < threshold
        corr_matrix = corr_matrix.where(~mask, np.nan)

    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns,
        y=corr_matrix.index,
        colorscale="RdBu_r",
        zmid=0,
        text=np.round(corr_matrix.values, 2),
        texttemplate="%{text}",
        textfont={"size": 10},
        hoverongaps=False
    ))

    fig.update_layout(
        title=title or "Correlation Matrix",
        xaxis_title="",
        yaxis_title="",
        template="plotly_white",
        height=max(400, len(columns) * 30)
    )

    return fig


def create_missing_heatmap(
    df: pd.DataFrame,
    max_rows: int = 100,
    title: Optional[str] = None
) -> go.Figure:
    """
    Create a missing values heatmap.

    Args:
        df: Input DataFrame
        max_rows: Maximum rows to display
        title: Optional title

    Returns:
        Plotly figure
    """
    # Sample if too many rows
    if len(df) > max_rows:
        sample_df = df.sample(max_rows, random_state=42)
    else:
        sample_df = df

    # Create missing matrix (1 = missing, 0 = present)
    missing_matrix = sample_df.isna().astype(int)

    fig = go.Figure(data=go.Heatmap(
        z=missing_matrix.values,
        x=missing_matrix.columns,
        y=list(range(len(missing_matrix))),
        colorscale=[[0, "white"], [1, "red"]],
        showscale=False,
        hoverongaps=False
    ))

    fig.update_layout(
        title=title or "Missing Values Pattern",
        xaxis_title="Columns",
        yaxis_title="Row Index",
        template="plotly_white",
        height=max(300, len(missing_matrix) * 3)
    )

    return fig


def create_distribution_comparison(
    df_before: pd.DataFrame,
    df_after: pd.DataFrame,
    column: str,
    bins: int = 30,
    title: Optional[str] = None
) -> go.Figure:
    """
    Create overlaid histogram comparing before/after distributions.

    Args:
        df_before: DataFrame before transformation
        df_after: DataFrame after transformation
        column: Column to compare
        bins: Number of bins
        title: Optional title

    Returns:
        Plotly figure
    """
    fig = go.Figure()

    # Before histogram
    data_before = df_before[column].dropna() if column in df_before.columns else pd.Series()
    if len(data_before) > 0:
        fig.add_trace(go.Histogram(
            x=data_before,
            nbinsx=bins,
            name="Before",
            opacity=0.5,
            marker_color="blue"
        ))

    # After histogram
    data_after = df_after[column].dropna() if column in df_after.columns else pd.Series()
    if len(data_after) > 0:
        fig.add_trace(go.Histogram(
            x=data_after,
            nbinsx=bins,
            name="After",
            opacity=0.5,
            marker_color="orange"
        ))

    fig.update_layout(
        title=title or f"Distribution Comparison: {column}",
        xaxis_title=column,
        yaxis_title="Count",
        barmode="overlay",
        showlegend=True,
        template="plotly_white"
    )

    return fig


def create_vif_bar_chart(
    vif_results: List[Dict[str, Any]],
    threshold: float = 10.0,
    title: Optional[str] = None
) -> go.Figure:
    """
    Create a bar chart of VIF values.

    Args:
        vif_results: List of VIF result dicts
        threshold: VIF threshold to highlight
        title: Optional title

    Returns:
        Plotly figure
    """
    columns = [r["column"] for r in vif_results]
    vif_values = [r["vif"] for r in vif_results]

    # Cap infinite values for display
    vif_display = [min(v, 100) if v != float("inf") else 100 for v in vif_values]

    colors = ["red" if v > threshold else "green" for v in vif_values]

    fig = go.Figure(data=go.Bar(
        x=columns,
        y=vif_display,
        marker_color=colors,
        text=[f"{v:.1f}" if v < 100 else ">100" for v in vif_values],
        textposition="outside"
    ))

    fig.add_hline(y=threshold, line_dash="dash", line_color="gray",
                  annotation_text=f"Threshold: {threshold}")

    fig.update_layout(
        title=title or "Variance Inflation Factor (VIF)",
        xaxis_title="Column",
        yaxis_title="VIF",
        template="plotly_white"
    )

    return fig


def create_outlier_boxplot(
    df: pd.DataFrame,
    column: str,
    bounds: tuple,
    title: Optional[str] = None
) -> go.Figure:
    """
    Create a boxplot with outlier bounds highlighted.

    Args:
        df: Input DataFrame
        column: Column to plot
        bounds: Tuple of (lower_bound, upper_bound)
        title: Optional title

    Returns:
        Plotly figure
    """
    data = df[column].dropna()

    fig = go.Figure()

    fig.add_trace(go.Box(
        y=data,
        name=column,
        boxpoints="outliers",
        marker_color="#4F8BF9"
    ))

    # Add bound lines
    if bounds[0] is not None:
        fig.add_hline(y=bounds[0], line_dash="dash", line_color="red",
                      annotation_text=f"Lower: {bounds[0]:.2f}")
    if bounds[1] is not None:
        fig.add_hline(y=bounds[1], line_dash="dash", line_color="red",
                      annotation_text=f"Upper: {bounds[1]:.2f}")

    fig.update_layout(
        title=title or f"Outlier Detection: {column}",
        yaxis_title=column,
        template="plotly_white"
    )

    return fig


def create_small_multiples(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    cols_per_row: int = 4,
    title: Optional[str] = None
) -> go.Figure:
    """
    Create small multiple histograms for multiple columns.

    Args:
        df: Input DataFrame
        columns: Columns to plot (None = all numeric)
        cols_per_row: Number of columns per row
        title: Optional title

    Returns:
        Plotly figure
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()[:12]

    n_cols = min(cols_per_row, len(columns))
    n_rows = (len(columns) + n_cols - 1) // n_cols

    fig = make_subplots(
        rows=n_rows,
        cols=n_cols,
        subplot_titles=columns,
        vertical_spacing=0.1,
        horizontal_spacing=0.05
    )

    for i, col in enumerate(columns):
        row = i // n_cols + 1
        col_idx = i % n_cols + 1

        data = df[col].dropna()
        if len(data) > 0:
            fig.add_trace(
                go.Histogram(x=data, name=col, showlegend=False, marker_color="#4F8BF9"),
                row=row, col=col_idx
            )

    fig.update_layout(
        title=title or "Distribution Overview",
        template="plotly_white",
        height=200 * n_rows
    )

    return fig
