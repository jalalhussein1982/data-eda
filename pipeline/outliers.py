"""Phase IV: Distribution Analysis & Outlier Handling."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from scipy import stats


def detect_outliers(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    method: str = "iqr",
    threshold: float = 1.5
) -> Dict[str, Any]:
    """
    Detect outliers in numerical columns.

    Args:
        df: Input DataFrame
        columns: Columns to analyze (None = all numeric)
        method: Detection method ('iqr', 'zscore', 'modified_zscore', 'percentile')
        threshold: Method-specific threshold

    Returns:
        Dict with outlier detection results per column
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    results = {}

    for col in columns:
        if col not in df.columns:
            continue

        col_data = df[col].dropna()

        if len(col_data) == 0:
            continue

        if method == "iqr":
            outlier_mask, bounds = detect_iqr_outliers(col_data, threshold)
        elif method == "zscore":
            outlier_mask, bounds = detect_zscore_outliers(col_data, threshold)
        elif method == "modified_zscore":
            outlier_mask, bounds = detect_modified_zscore_outliers(col_data, threshold)
        elif method == "percentile":
            outlier_mask, bounds = detect_percentile_outliers(col_data, threshold)
        else:
            raise ValueError(f"Unknown method: {method}")

        outlier_count = outlier_mask.sum()
        outlier_indices = col_data[outlier_mask].index.tolist()

        results[col] = {
            "outlier_count": int(outlier_count),
            "outlier_pct": round((outlier_count / len(col_data)) * 100, 2),
            "lower_bound": float(bounds[0]) if bounds[0] is not None else None,
            "upper_bound": float(bounds[1]) if bounds[1] is not None else None,
            "outlier_indices": outlier_indices[:20],
            "outlier_values": col_data[outlier_mask].head(20).tolist(),
            "statistics": {
                "mean": float(col_data.mean()),
                "median": float(col_data.median()),
                "std": float(col_data.std()),
                "min": float(col_data.min()),
                "max": float(col_data.max()),
                "skewness": float(col_data.skew()),
                "kurtosis": float(col_data.kurtosis())
            }
        }

    return {
        "method": method,
        "threshold": threshold,
        "columns_analyzed": len(results),
        "total_outliers": sum(r["outlier_count"] for r in results.values()),
        "results": results
    }


def detect_iqr_outliers(
    data: pd.Series,
    multiplier: float = 1.5
) -> Tuple[pd.Series, Tuple[float, float]]:
    """Detect outliers using IQR method."""
    Q1 = data.quantile(0.25)
    Q3 = data.quantile(0.75)
    IQR = Q3 - Q1

    lower_bound = Q1 - (multiplier * IQR)
    upper_bound = Q3 + (multiplier * IQR)

    outlier_mask = (data < lower_bound) | (data > upper_bound)

    return outlier_mask, (lower_bound, upper_bound)


def detect_zscore_outliers(
    data: pd.Series,
    threshold: float = 3.0
) -> Tuple[pd.Series, Tuple[float, float]]:
    """Detect outliers using Z-score method."""
    z_scores = np.abs(stats.zscore(data))
    outlier_mask = z_scores > threshold

    mean = data.mean()
    std = data.std()
    lower_bound = mean - (threshold * std)
    upper_bound = mean + (threshold * std)

    return pd.Series(outlier_mask, index=data.index), (lower_bound, upper_bound)


def detect_modified_zscore_outliers(
    data: pd.Series,
    threshold: float = 3.5
) -> Tuple[pd.Series, Tuple[float, float]]:
    """Detect outliers using Modified Z-score (MAD-based)."""
    median = data.median()
    mad = np.median(np.abs(data - median))

    if mad == 0:
        return pd.Series(False, index=data.index), (median, median)

    modified_z = 0.6745 * (data - median) / mad
    outlier_mask = np.abs(modified_z) > threshold

    lower_bound = median - (threshold * mad / 0.6745)
    upper_bound = median + (threshold * mad / 0.6745)

    return outlier_mask, (lower_bound, upper_bound)


def detect_percentile_outliers(
    data: pd.Series,
    percentile: float = 1.0
) -> Tuple[pd.Series, Tuple[float, float]]:
    """Detect outliers using percentile cutoffs."""
    lower_bound = data.quantile(percentile / 100)
    upper_bound = data.quantile(1 - percentile / 100)

    outlier_mask = (data < lower_bound) | (data > upper_bound)

    return outlier_mask, (lower_bound, upper_bound)


def resolve_outliers(
    df: pd.DataFrame,
    resolution_config: Dict[str, Dict[str, Any]],
    method: str = "iqr",
    threshold: float = 1.5
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Resolve outliers based on specified strategies.

    Args:
        df: Input DataFrame
        resolution_config: Dict mapping column names to resolution config
                          {"action": "keep|drop|winsorize", "lower_pct": 1, "upper_pct": 99}
        method: Detection method
        threshold: Detection threshold

    Returns:
        Tuple of (cleaned DataFrame, resolution stats)
    """
    df = df.copy()
    stats = {"resolutions_applied": []}
    rows_to_drop = set()

    for column, config in resolution_config.items():
        if column not in df.columns:
            continue

        action = config.get("action", "keep")

        if action == "keep":
            stats["resolutions_applied"].append({
                "column": column,
                "action": "keep",
                "changes": 0
            })
            continue

        col_data = df[column].dropna()

        if method == "iqr":
            outlier_mask, bounds = detect_iqr_outliers(col_data, threshold)
        elif method == "zscore":
            outlier_mask, bounds = detect_zscore_outliers(col_data, threshold)
        elif method == "modified_zscore":
            outlier_mask, bounds = detect_modified_zscore_outliers(col_data, threshold)
        else:
            outlier_mask, bounds = detect_iqr_outliers(col_data, threshold)

        outlier_count = outlier_mask.sum()

        if action == "drop":
            rows_to_drop.update(col_data[outlier_mask].index.tolist())
            stats["resolutions_applied"].append({
                "column": column,
                "action": "drop",
                "rows_marked": int(outlier_count)
            })

        elif action == "winsorize":
            lower_pct = config.get("lower_pct", 1)
            upper_pct = config.get("upper_pct", 99)

            lower_val = df[column].quantile(lower_pct / 100)
            upper_val = df[column].quantile(upper_pct / 100)

            df[column] = df[column].clip(lower=lower_val, upper=upper_val)

            stats["resolutions_applied"].append({
                "column": column,
                "action": "winsorize",
                "lower_bound": float(lower_val),
                "upper_bound": float(upper_val),
                "values_clipped": int(outlier_count)
            })

    # Apply row drops
    if rows_to_drop:
        df = df.drop(index=list(rows_to_drop))
        stats["total_rows_dropped"] = len(rows_to_drop)

    stats["rows_after_resolution"] = len(df)

    return df, stats


def get_outlier_summary(
    df: pd.DataFrame,
    method: str = "iqr",
    threshold: float = 1.5
) -> Dict[str, Any]:
    """
    Get summary of outliers in numerical columns.

    Returns:
        Dict with outlier summary
    """
    detection = detect_outliers(df, method=method, threshold=threshold)

    summary = {
        "method": method,
        "threshold": threshold,
        "columns_with_outliers": 0,
        "total_outliers": 0,
        "column_summaries": []
    }

    for col, result in detection["results"].items():
        if result["outlier_count"] > 0:
            summary["columns_with_outliers"] += 1
            summary["total_outliers"] += result["outlier_count"]

            summary["column_summaries"].append({
                "column": col,
                "outlier_count": result["outlier_count"],
                "outlier_pct": result["outlier_pct"],
                "bounds": [result["lower_bound"], result["upper_bound"]],
                "stats": result["statistics"]
            })

    return summary


def get_distribution_stats(df: pd.DataFrame, column: str) -> Dict[str, Any]:
    """Get distribution statistics for a single column."""
    if column not in df.columns:
        return {"error": f"Column '{column}' not found"}

    col_data = df[column].dropna()

    if not pd.api.types.is_numeric_dtype(col_data):
        return {
            "column": column,
            "type": "categorical",
            "unique_count": int(col_data.nunique()),
            "mode": str(col_data.mode().iloc[0]) if len(col_data.mode()) > 0 else None,
            "value_counts": col_data.value_counts().head(10).to_dict()
        }

    return {
        "column": column,
        "type": "numeric",
        "count": int(len(col_data)),
        "mean": float(col_data.mean()),
        "median": float(col_data.median()),
        "std": float(col_data.std()),
        "min": float(col_data.min()),
        "max": float(col_data.max()),
        "skewness": float(col_data.skew()),
        "kurtosis": float(col_data.kurtosis()),
        "percentiles": {
            "1%": float(col_data.quantile(0.01)),
            "5%": float(col_data.quantile(0.05)),
            "25%": float(col_data.quantile(0.25)),
            "50%": float(col_data.quantile(0.50)),
            "75%": float(col_data.quantile(0.75)),
            "95%": float(col_data.quantile(0.95)),
            "99%": float(col_data.quantile(0.99))
        }
    }
