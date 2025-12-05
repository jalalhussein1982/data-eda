"""Phase II: Scope Definition (Dimensionality Reduction)."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any


def get_column_recommendations(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Analyze columns and provide recommendations for scope selection.

    Returns:
        Dict mapping column names to analysis results with recommendations
    """
    recommendations = {}

    for col in df.columns:
        col_data = df[col]
        dtype = str(col_data.dtype)
        unique_count = col_data.nunique()
        null_count = col_data.isna().sum()
        total_rows = len(df)

        flags = []
        recommendation = "keep"

        # Check for zero variance
        if unique_count <= 1:
            flags.append({
                "type": "zero_variance",
                "severity": "high",
                "message": "Only 1 unique value - no analytical value"
            })
            recommendation = "drop"

        # Check for high cardinality / potential ID
        elif unique_count == total_rows:
            flags.append({
                "type": "high_cardinality",
                "severity": "medium",
                "message": "Unique values equal row count - likely identifier"
            })
            recommendation = "review"

        # Check for near-zero variance
        elif dtype in ["object", "category"]:
            mode_count = col_data.value_counts().iloc[0] if len(col_data.value_counts()) > 0 else 0
            mode_pct = (mode_count / total_rows) * 100
            if mode_pct > 95:
                flags.append({
                    "type": "near_zero_variance",
                    "severity": "medium",
                    "message": f"{mode_pct:.1f}% of values are single value"
                })
                recommendation = "review"

        # Check for high missing rate
        null_pct = (null_count / total_rows) * 100
        if null_pct > 50:
            flags.append({
                "type": "high_missing",
                "severity": "medium",
                "message": f"{null_pct:.1f}% missing values"
            })
            recommendation = "review"

        recommendations[col] = {
            "dtype": dtype,
            "unique_count": int(unique_count),
            "null_count": int(null_count),
            "null_pct": round(null_pct, 2),
            "flags": flags,
            "recommendation": recommendation
        }

    return recommendations


def apply_scope_selection(
    df: pd.DataFrame,
    selected_columns: List[str],
    drop_zero_variance: bool = True,
    drop_high_cardinality: bool = False
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Apply scope selection to DataFrame.

    Args:
        df: Input DataFrame
        selected_columns: Columns to keep
        drop_zero_variance: Auto-drop columns with 1 unique value
        drop_high_cardinality: Auto-drop columns where unique == row count

    Returns:
        Tuple of (scoped DataFrame, selection stats)
    """
    original_cols = list(df.columns)

    # Start with selected columns
    if selected_columns:
        columns_to_keep = [c for c in selected_columns if c in df.columns]
    else:
        columns_to_keep = list(df.columns)

    auto_dropped = []

    # Apply automatic filters
    if drop_zero_variance:
        for col in columns_to_keep[:]:
            if df[col].nunique() <= 1:
                columns_to_keep.remove(col)
                auto_dropped.append({"column": col, "reason": "zero_variance"})

    if drop_high_cardinality:
        for col in columns_to_keep[:]:
            if df[col].nunique() == len(df):
                columns_to_keep.remove(col)
                auto_dropped.append({"column": col, "reason": "high_cardinality"})

    df_scoped = df[columns_to_keep].copy()

    stats = {
        "original_columns": len(original_cols),
        "selected_columns": len(columns_to_keep),
        "dropped_columns": len(original_cols) - len(columns_to_keep),
        "auto_dropped": auto_dropped,
        "kept_columns": columns_to_keep
    }

    return df_scoped, stats


def get_column_summary(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Get summary information for each column.

    Returns:
        List of column summaries
    """
    summaries = []

    for col in df.columns:
        col_data = df[col]
        dtype = str(col_data.dtype)
        unique_count = col_data.nunique()
        null_count = col_data.isna().sum()

        summary = {
            "column": col,
            "dtype": dtype,
            "unique_count": int(unique_count),
            "null_count": int(null_count),
            "null_pct": round((null_count / len(df)) * 100, 2) if len(df) > 0 else 0
        }

        # Add numeric stats
        if pd.api.types.is_numeric_dtype(col_data):
            summary.update({
                "min": float(col_data.min()) if not col_data.isna().all() else None,
                "max": float(col_data.max()) if not col_data.isna().all() else None,
                "mean": float(col_data.mean()) if not col_data.isna().all() else None
            })

        # Add categorical stats
        if dtype in ["object", "category"] or unique_count <= 20:
            top_values = col_data.value_counts().head(5).to_dict()
            summary["top_values"] = {str(k): int(v) for k, v in top_values.items()}

        summaries.append(summary)

    return summaries
